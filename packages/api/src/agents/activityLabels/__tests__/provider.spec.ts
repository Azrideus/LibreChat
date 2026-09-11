import { GraphEvents } from '@librechat/agents';
import { ActivityLabelEvents, ContentTypes } from 'librechat-data-provider';
import type { TMessageContentParts, TActivityLabelEvent } from 'librechat-data-provider';
import type { AppConfig } from '@librechat/data-schemas';
import type { EventHandler } from '@librechat/agents';
import { createProviderLabelEventWiring } from '../provider';

const endpoint = 'Turing Agents';

function appConfig(overrides: Record<string, unknown> = {}): AppConfig {
  return {
    endpoints: {
      custom: [{ name: endpoint, providerLabelEvents: true, ...overrides }],
    },
  } as unknown as AppConfig;
}

function providerChunk(index: number, part: Record<string, unknown>): unknown {
  return {
    chunk: {
      additional_kwargs: {
        provider_specific_fields: {
          librechat_event: {
            event: ActivityLabelEvents.ON_ACTIVITY_LABEL,
            data: { index, part },
          },
        },
      },
    },
  };
}

async function dispatch(handler: EventHandler, data: unknown): Promise<void> {
  await handler.handle(GraphEvents.CHAT_MODEL_STREAM, data as never);
}

describe('createProviderLabelEventWiring', () => {
  it('is disabled unless the matching custom endpoint opts in', () => {
    const options = {
      endpoint,
      getContentParts: () => [],
      bumpIndexOffset: jest.fn(),
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent: jest.fn(async () => undefined),
    };

    expect(createProviderLabelEventWiring({ ...options, appConfig: appConfig() })).toBeDefined();
    expect(
      createProviderLabelEventWiring({
        ...options,
        appConfig: appConfig({ providerLabelEvents: false }),
      }),
    ).toBeUndefined();
    expect(
      createProviderLabelEventWiring({ ...options, appConfig: appConfig(), endpoint: 'Other' }),
    ).toBeUndefined();
  });

  it('installs its own chat-model-stream handler when the default handler set has none', async () => {
    // The real browser-chat handler set (getDefaultHandlers in
    // api/server/controllers/agents/callbacks.js) never registers
    // on_chat_model_stream — content reaches the client via
    // on_message_delta/on_run_step_delta instead. This wiring must still
    // fire in that case, not silently no-op waiting for a handler to wrap.
    const parts: TMessageContentParts[] = [];
    const emitLabelEvent = jest.fn(async (_event: TActivityLabelEvent) => undefined);
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset: jest.fn(),
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent,
    });
    const handlers = wiring?.handlers({
      [GraphEvents.ON_MESSAGE_DELTA]: { handle: jest.fn() },
    });
    const handler = handlers?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;

    expect(handler).toBeDefined();
    await dispatch(
      handler,
      providerChunk(0, { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'No prior handler' }),
    );

    expect(parts).toEqual([
      { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'No prior handler' },
    ]);
    expect(emitLabelEvent).toHaveBeenCalledWith({ index: 0, part: parts[0] });
  });

  it('handles normal content first, allocates a host index, and sanitizes a phase label', async () => {
    const parts: TMessageContentParts[] = [];
    const bumpIndexOffset = jest.fn();
    const emitLabelEvent = jest.fn(async (_event: TActivityLabelEvent) => undefined);
    const originalHandle = jest.fn(async () => {
      parts.push({ type: ContentTypes.THINK, think: 'Inspecting the board' });
    });
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset,
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent,
    });
    const handlers = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: originalHandle },
    });

    await dispatch(
      handlers?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler,
      providerChunk(41, {
        type: ContentTypes.ACTIVITY_LABEL,
        activity_label: `  Reviewed   board state  \nignore this line`,
        activity_label_type: 'phase',
        activity_start_index: 0,
        activity_end_index: 1,
        activity_count: 1,
        agent_ids: ['agent-1'],
        counts: { searches: 1, reads: 2, writes: 0, commands: 0, other: 0 },
        status: 'ok',
        unknown: 'discard me',
      }),
    );

    expect(originalHandle).toHaveBeenCalledTimes(1);
    expect(parts).toEqual([
      { type: ContentTypes.THINK, think: 'Inspecting the board' },
      {
        type: ContentTypes.ACTIVITY_LABEL,
        activity_label: 'Reviewed board state',
        activity_label_type: 'phase',
        activity_start_index: 0,
        activity_end_index: 1,
        activity_count: 1,
        agent_ids: ['agent-1'],
        counts: { searches: 1, reads: 2, writes: 0, commands: 0, other: 0 },
        status: 'ok',
      },
    ]);
    expect(bumpIndexOffset).toHaveBeenCalledTimes(1);
    expect(emitLabelEvent).toHaveBeenCalledWith({
      index: 1,
      part: parts[1],
    });
  });

  it('updates the same allocated slot when a provider index is repeated', async () => {
    const parts: TMessageContentParts[] = [];
    const bumpIndexOffset = jest.fn();
    const emitLabelEvent = jest.fn(async (_event: TActivityLabelEvent) => undefined);
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset,
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent,
    });
    const handler = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: jest.fn() },
    })?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;

    await dispatch(
      handler,
      providerChunk(7, {
        type: ContentTypes.ACTIVITY_LABEL,
        activity_label: '',
        pending: true,
      }),
    );
    await dispatch(
      handler,
      providerChunk(7, {
        type: ContentTypes.ACTIVITY_LABEL,
        activity_label: 'Read the datasheets',
        pending: false,
      }),
    );

    expect(parts).toEqual([
      {
        type: ContentTypes.ACTIVITY_LABEL,
        activity_label: 'Read the datasheets',
        pending: false,
      },
    ]);
    expect(bumpIndexOffset).toHaveBeenCalledTimes(1);
    expect(emitLabelEvent).toHaveBeenNthCalledWith(2, {
      index: 0,
      part: parts[0],
    });
  });

  it('also accepts the SDK chat-generation wrapper form', async () => {
    const parts: TMessageContentParts[] = [];
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset: jest.fn(),
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent: jest.fn(async () => undefined),
    });
    const handler = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: jest.fn() },
    })?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;
    const direct = providerChunk(9, {
      type: ContentTypes.ACTIVITY_LABEL,
      activity_label: 'Wrapped generation',
    }) as { chunk: unknown };

    await dispatch(handler, { chunk: { message: direct.chunk } });

    expect(parts).toEqual([
      { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'Wrapped generation' },
    ]);
  });

  it('enforces the configured distinct-label cap', async () => {
    const parts: TMessageContentParts[] = [];
    const emitLabelEvent = jest.fn(async (_event: TActivityLabelEvent) => undefined);
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig({ activityMaxPerRun: 1 }),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset: jest.fn(),
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent,
    });
    const handler = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: jest.fn() },
    })?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;

    await dispatch(
      handler,
      providerChunk(1, { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'First' }),
    );
    await dispatch(
      handler,
      providerChunk(2, { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'Second' }),
    );

    expect(parts).toHaveLength(1);
    expect(emitLabelEvent).toHaveBeenCalledTimes(1);
  });

  it('ignores malformed or unrecognized envelopes after normal stream handling', async () => {
    const parts: TMessageContentParts[] = [];
    const emitLabelEvent = jest.fn(async (_event: TActivityLabelEvent) => undefined);
    const originalHandle = jest.fn();
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset: jest.fn(),
      rollbackIndexOffset: jest.fn(),
      emitLabelEvent,
    });
    const handler = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: originalHandle },
    })?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;

    await dispatch(
      handler,
      providerChunk(0, { type: ContentTypes.ACTIVITY_LABEL, activity_label: 123 }),
    );
    await dispatch(handler, { chunk: { additional_kwargs: {} } });

    expect(originalHandle).toHaveBeenCalledTimes(2);
    expect(parts).toEqual([]);
    expect(emitLabelEvent).not.toHaveBeenCalled();
  });

  it('rolls back an unpersisted new slot without failing the model stream', async () => {
    const parts: TMessageContentParts[] = [];
    const error = new Error('stream store unavailable');
    const bumpIndexOffset = jest.fn();
    const rollbackIndexOffset = jest.fn();
    const onError = jest.fn();
    const wiring = createProviderLabelEventWiring({
      appConfig: appConfig(),
      endpoint,
      getContentParts: () => parts,
      bumpIndexOffset,
      rollbackIndexOffset,
      emitLabelEvent: jest.fn(async () => {
        throw error;
      }),
      onError,
    });
    const handler = wiring?.handlers({
      [GraphEvents.CHAT_MODEL_STREAM]: { handle: jest.fn() },
    })?.[GraphEvents.CHAT_MODEL_STREAM] as EventHandler;

    await expect(
      dispatch(
        handler,
        providerChunk(3, { type: ContentTypes.ACTIVITY_LABEL, activity_label: 'Attempted label' }),
      ),
    ).resolves.toBeUndefined();

    expect(parts).toEqual([]);
    expect(bumpIndexOffset).toHaveBeenCalledTimes(1);
    expect(rollbackIndexOffset).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(error);
  });
});
