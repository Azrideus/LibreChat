import { GraphEvents } from '@librechat/agents';
import { ActivityLabelEvents, ContentTypes } from 'librechat-data-provider';
import type {
  TActivityLabelEvent,
  TMessageContentParts,
  TProviderLabelEvent,
} from 'librechat-data-provider';
import type { AppConfig } from '@librechat/data-schemas';
import type { EventHandler } from '@librechat/agents';
import { getCustomEndpointConfig } from '~/app/config';
import { normalizeLabelOutput } from './runtime';

const DEFAULT_MAX_LABELS = 20;
const MAX_LABEL_REFERENCES = 100;
const MAX_REFERENCE_LENGTH = 256;

type LabelPart = TActivityLabelEvent['part'];

type ProviderLabelEndpoint = {
  providerLabelEvents?: boolean;
  activityMaxPerRun?: number;
};

interface ProviderLabelEventWiringOptions {
  appConfig?: AppConfig;
  endpoint?: string;
  getContentParts: () => Array<TMessageContentParts | null | undefined>;
  bumpIndexOffset: () => void;
  rollbackIndexOffset: () => void;
  emitLabelEvent: (event: TActivityLabelEvent) => Promise<unknown>;
  onError?: (error: unknown) => void;
}

export interface ProviderLabelEventWiring {
  handlers: (
    handlers: Record<string, EventHandler> | undefined,
  ) => Record<string, EventHandler> | undefined;
}

function isObject(value: unknown): value is { [key: string]: unknown } {
  return typeof value === 'object' && value != null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0
    ? value.slice(0, MAX_REFERENCE_LENGTH)
    : undefined;
}

function optionalIndex(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : undefined;
}

function optionalStringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const strings = value
    .filter((item): item is string => typeof item === 'string' && item.length > 0)
    .slice(0, MAX_LABEL_REFERENCES)
    .map((item) => item.slice(0, MAX_REFERENCE_LENGTH));
  return strings.length > 0 ? strings : undefined;
}

function normalizeCounts(value: unknown): LabelPart['counts'] | undefined {
  if (!isObject(value)) {
    return undefined;
  }
  const keys = ['searches', 'reads', 'writes', 'commands', 'other'] as const;
  return Object.fromEntries(
    keys.map((key) => [key, optionalIndex(value[key]) ?? 0]),
  ) as NonNullable<LabelPart['counts']>;
}

function normalizeLabelPart(value: unknown): LabelPart | undefined {
  if (
    !isObject(value) ||
    value.type !== ContentTypes.ACTIVITY_LABEL ||
    typeof value[ContentTypes.ACTIVITY_LABEL] !== 'string'
  ) {
    return undefined;
  }
  const label = normalizeLabelOutput(value[ContentTypes.ACTIVITY_LABEL]);
  const status =
    value.status === 'ok' || value.status === 'partial' || value.status === 'failed'
      ? value.status
      : undefined;
  const activityLabelType = value.activity_label_type === 'phase' ? 'phase' : undefined;
  const activityStartIndex = optionalIndex(value.activity_start_index);
  const activityEndIndex = optionalIndex(value.activity_end_index);
  const activityCount = optionalIndex(value.activity_count);
  const toolCallIds = optionalStringList(value.tool_call_ids);
  const agentIds = optionalStringList(value.agent_ids);
  const agentId = optionalString(value.agentId);
  const counts = normalizeCounts(value.counts);
  return {
    type: ContentTypes.ACTIVITY_LABEL,
    [ContentTypes.ACTIVITY_LABEL]: label,
    ...(activityLabelType != null && { activity_label_type: activityLabelType }),
    ...(toolCallIds != null && { tool_call_ids: toolCallIds }),
    ...(activityStartIndex != null && { activity_start_index: activityStartIndex }),
    ...(activityEndIndex != null && { activity_end_index: activityEndIndex }),
    ...(activityCount != null && { activity_count: activityCount }),
    ...(agentIds != null && { agent_ids: agentIds }),
    ...(counts != null && { counts }),
    ...(status != null && { status }),
    ...(agentId != null && { agentId }),
    ...(typeof value.pending === 'boolean' && { pending: value.pending }),
  };
}

function parseProviderLabelEvent(data: unknown): TProviderLabelEvent | undefined {
  if (!isObject(data) || !isObject(data.chunk)) {
    return undefined;
  }
  /** `StreamEventData.chunk` is either an AIMessageChunk directly (the
   *  normal `on_chat_model_stream` form) or a ChatGenerationChunk wrapping
   *  one under `message`. */
  const message = isObject(data.chunk.message) ? data.chunk.message : data.chunk;
  const kwargs = message.additional_kwargs;
  if (!isObject(kwargs) || !isObject(kwargs.provider_specific_fields)) {
    return undefined;
  }
  const envelope = kwargs.provider_specific_fields.librechat_event;
  if (
    !isObject(envelope) ||
    envelope.event !== ActivityLabelEvents.ON_ACTIVITY_LABEL ||
    !isObject(envelope.data)
  ) {
    return undefined;
  }
  const index = optionalIndex(envelope.data.index);
  const part = normalizeLabelPart(envelope.data.part);
  if (index == null || part == null) {
    return undefined;
  }
  return {
    event: ActivityLabelEvents.ON_ACTIVITY_LABEL,
    data: { index, part },
  };
}

export function createProviderLabelEventWiring(
  options: ProviderLabelEventWiringOptions,
): ProviderLabelEventWiring | undefined {
  if (!options.appConfig || !options.endpoint) {
    return undefined;
  }
  let endpointConfig: Partial<ProviderLabelEndpoint> | undefined;
  try {
    endpointConfig = getCustomEndpointConfig({
      endpoint: options.endpoint,
      appConfig: options.appConfig,
    }) as Partial<ProviderLabelEndpoint> | undefined;
  } catch {
    return undefined;
  }
  if (endpointConfig?.providerLabelEvents !== true) {
    return undefined;
  }

  const maxLabels = endpointConfig.activityMaxPerRun ?? DEFAULT_MAX_LABELS;
  const providerIndices = new Map<number, number>();

  const apply = async (providerEvent: TProviderLabelEvent): Promise<void> => {
    const providerIndex = providerEvent.data.index;
    const parts = options.getContentParts();
    const existingIndex = providerIndices.get(providerIndex);
    if (existingIndex != null) {
      const event = { ...providerEvent.data, index: existingIndex };
      try {
        await options.emitLabelEvent(event);
        parts[existingIndex] = event.part;
      } catch (error) {
        options.onError?.(error);
      }
      return;
    }
    if (providerIndices.size >= maxLabels) {
      return;
    }

    const index = parts.length;
    const event = { ...providerEvent.data, index };
    parts.push(event.part);
    options.bumpIndexOffset();
    try {
      await options.emitLabelEvent(event);
      providerIndices.set(providerIndex, index);
    } catch (error) {
      if (parts[index] === event.part) {
        parts.splice(index, 1);
        options.rollbackIndexOffset();
      }
      options.onError?.(error);
    }
  };

  return {
    handlers: (handlers) => {
      if (!handlers) {
        return handlers;
      }
      /**
       * The default browser-chat handler set has no `on_chat_model_stream`
       * entry — content reaches the client via `on_message_delta` /
       * `on_run_step_delta` instead — so this must install its own handler
       * rather than only wrapping one that may not exist; chaining into an
       * existing handler (e.g. from a future default) still runs first.
       */
      const streamHandler = handlers[GraphEvents.CHAT_MODEL_STREAM];
      return {
        ...handlers,
        [GraphEvents.CHAT_MODEL_STREAM]: {
          handle: async (event, data, metadata, graph) => {
            const result = streamHandler
              ? await streamHandler.handle(event, data, metadata, graph)
              : undefined;
            const providerEvent = parseProviderLabelEvent(data);
            if (providerEvent != null) {
              await apply(providerEvent);
            }
            return result;
          },
        },
      };
    },
  };
}
