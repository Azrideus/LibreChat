"""
Minimal OpenAI-compatible LangGraph server for testing LibreChat's
providerLabelEvents bridge (packages/api/src/agents/activityLabels/provider.ts).

It exposes POST /v1/chat/completions (streaming only) and, for a two-node
LangGraph run, emits:
  1. an "activity_label" for the plan node (activity_label_type unset -> a
     normal batch label)
  2. an "activity_label" for the answer node with activity_label_type="phase"
  3. the actual assistant text

Each label rides inside the OpenAI SSE delta as
delta.provider_specific_fields.librechat_event, exactly what LibreChat's
ChatOpenAI fork (@librechat/agents) copies into additional_kwargs and what
provider.ts parses back out.

Run:
    pip install fastapi uvicorn langgraph
    python tests/turing_agents_activity_label.py

Point librechat.yaml's "Turing Agents" endpoint baseURL at this server
(http://localhost:8093/v1), send a message, and confirm the two activity
labels appear above the assistant reply in the UI.
"""

import json
import time
import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    label: str


def plan(state: State) -> State:
    return {"label": "Understanding the request"}


def answer(state: State) -> State:
    return {"label": "Drafting the reply"}


graph = StateGraph(State)
graph.add_node("plan", plan)
graph.add_node("answer", answer)
graph.set_entry_point("plan")
graph.add_edge("plan", "answer")
graph.add_edge("answer", END)
app_graph = graph.compile()

app = FastAPI()


def sse_chunk(model: str, delta: dict) -> str:
    payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def activity_label_delta(index: int, label: str, phase: bool = False) -> dict:
    part = {"type": "activity_label", "activity_label": label}
    if phase:
        part["activity_label_type"] = "phase"
    return {
        "provider_specific_fields": {
            "librechat_event": {
                "event": "on_activity_label",
                "data": {"index": index, "part": part},
            }
        }
    }


def stream_response(model: str):
    state: State = {"label": ""}
    label_index = 0

    for node_name in ("plan", "answer"):
        state = {**state, **app_graph.nodes[node_name].invoke(state)}
        yield sse_chunk(
            model,
            activity_label_delta(label_index, state["label"], phase=(node_name == "answer")),
        )
        label_index += 1

    reply = "This is a test reply from the Turing Agents test server."
    yield sse_chunk(model, {"role": "assistant", "content": ""})
    for word in reply.split(" "):
        yield sse_chunk(model, {"content": word + " "})

    yield sse_chunk(model, {})
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(body: dict):
    model = body.get("model", "TuringSimple")
    return StreamingResponse(stream_response(model), media_type="text/event-stream")


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [{"id": "TuringSimple", "object": "model", "owned_by": "turing-agents"}],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8093)
