import { AChatAgent, AChatApiError, ChatRequest, ChatResult } from './types';

const API_PREFIX = '/api/agents/v1';
const CONNECT_TIMEOUT_MS = 30_000;
const STREAM_IDLE_TIMEOUT_MS = 90_000;

export function normalizeBaseUrl(input: string): string {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    throw new AChatApiError('AChat URL must be a valid HTTPS URL, or HTTP on localhost.');
  }
  const isLoopback = ['localhost', '127.0.0.1', '[::1]', '::1'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && isLoopback)) || url.username || url.password) {
    throw new AChatApiError('AChat URL must use HTTPS, or HTTP on localhost, and must not contain credentials.');
  }
  return url.origin;
}

interface ModelsResponse {
  data?: Array<{
    id?: unknown;
    name?: unknown;
    description?: unknown;
    provider?: unknown;
  }>;
}

interface StreamChunk {
  choices?: Array<{
    delta?: { content?: unknown };
    finish_reason?: string | null;
  }>;
  usage?: ChatResult['usage'];
  error?: { message?: string };
}

export class AChatClient {
  private readonly baseUrl: URL;

  constructor(baseUrl: string, private readonly apiKey: string) {
    this.baseUrl = new URL(normalizeBaseUrl(baseUrl));
  }

  async listAgents(signal?: AbortSignal): Promise<AChatAgent[]> {
    const response = await this.fetchWithTimeout(`${API_PREFIX}/models`, { method: 'GET' }, signal);
    if (!response.ok) {
      throw await this.responseError(response);
    }

    let payload: ModelsResponse;
    try {
      payload = await response.json() as ModelsResponse;
    } catch {
      throw new AChatApiError('AChat returned an unreadable agent list. Check the configured server URL.');
    }
    if (!Array.isArray(payload.data)) {
      throw new AChatApiError('AChat returned an unexpected agent list.');
    }
    return payload.data.flatMap((row): AChatAgent[] => {
      if (typeof row.id !== 'string' || !row.id) {
        return [];
      }
      return [{
        id: row.id,
        name: typeof row.name === 'string' && row.name ? row.name : row.id,
        ...(typeof row.description === 'string' ? { description: row.description } : {}),
        ...(typeof row.provider === 'string' ? { provider: row.provider } : {}),
      }];
    });
  }

  async streamChat(
    request: ChatRequest,
    onDelta: (text: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatResult> {
    const response = await this.fetchWithTimeout(`${API_PREFIX}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    }, signal);
    if (!response.ok) {
      throw await this.responseError(response);
    }
    if (!response.body) {
      throw new AChatApiError('AChat returned an empty response stream.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finishReason: string | null | undefined;
    let usage: ChatResult['usage'];
    let done = false;
    let timedOut = false;
    let streamTimer: ReturnType<typeof setTimeout> | undefined;
    const resetStreamTimeout = () => {
      if (streamTimer) clearTimeout(streamTimer);
      streamTimer = setTimeout(() => {
        timedOut = true;
        void reader.cancel();
      }, STREAM_IDLE_TIMEOUT_MS);
    };
    const cancelOnAbort = () => { void reader.cancel(); };
    signal?.addEventListener('abort', cancelOnAbort, { once: true });
    resetStreamTimeout();

    const consumeLine = (line: string): void => {
      const normalized = line.endsWith('\r') ? line.slice(0, -1) : line;
      if (!normalized.startsWith('data:')) {
        return;
      }
      const data = normalized.slice(5).trimStart();
      if (!data || data === '[DONE]') {
        if (data === '[DONE]') {
          done = true;
        }
        return;
      }
      let chunk: StreamChunk;
      try {
        chunk = JSON.parse(data) as StreamChunk;
      } catch {
        throw new AChatApiError('AChat sent an invalid streaming response.');
      }
      if (chunk.error?.message) {
        throw new AChatApiError(chunk.error.message.slice(0, 300));
      }
      const choice = chunk.choices?.[0];
      const content = choice?.delta?.content;
      if (typeof content === 'string') {
        onDelta(content);
      } else if (Array.isArray(content)) {
        for (const item of content) {
          if (item && typeof item === 'object' && 'text' in item && typeof item.text === 'string') {
            onDelta(item.text);
          }
        }
      }
      if (choice?.finish_reason !== undefined) {
        finishReason = choice.finish_reason;
      }
      if (chunk.usage) {
        usage = chunk.usage;
      }
    };

    try {
      while (!done) {
        if (signal?.aborted) {
          await reader.cancel();
          throw new AChatApiError('AChat request cancelled.');
        }
        const { value, done: streamEnded } = await reader.read();
        resetStreamTimeout();
        if (value) {
          buffer += decoder.decode(value, { stream: !streamEnded });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            consumeLine(line);
            if (done) {
              break;
            }
          }
        }
        if (streamEnded) {
          if (buffer) {
            consumeLine(buffer);
          }
          break;
        }
      }
      if (signal?.aborted) {
        throw new AChatApiError('AChat request cancelled.');
      }
      if (timedOut) {
        throw new AChatApiError('AChat stopped responding. Check the connection and try again.');
      }
    } finally {
      if (streamTimer) clearTimeout(streamTimer);
      signal?.removeEventListener('abort', cancelOnAbort);
      reader.releaseLock();
    }
    return { finishReason, usage };
  }

  private async fetchWithTimeout(path: string, init: RequestInit, externalSignal?: AbortSignal): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(new Error('AChat request timed out.')), CONNECT_TIMEOUT_MS);
    const abortFromCaller = () => controller.abort(externalSignal?.reason);
    externalSignal?.addEventListener('abort', abortFromCaller, { once: true });
    try {
      const response = await fetch(new URL(path, this.baseUrl), {
        ...init,
        redirect: 'error',
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          ...init.headers,
        },
      });
      return response;
    } catch (error) {
      if (externalSignal?.aborted) {
        throw new AChatApiError('AChat request cancelled.');
      }
      if (controller.signal.aborted) {
        throw new AChatApiError('AChat request timed out. Check the URL and connection, then try again.');
      }
      if (error instanceof TypeError) {
        throw new AChatApiError('Could not connect to AChat. Check the configured URL and make sure the tunnel is active.');
      }
      throw new AChatApiError('Could not connect to AChat. Check the configured URL and connection.');
    } finally {
      clearTimeout(timeout);
      externalSignal?.removeEventListener('abort', abortFromCaller);
    }
  }

  private async responseError(response: Response): Promise<AChatApiError> {
    const status = response.status;
    if (status === 401) {
      return new AChatApiError('AChat rejected the Agent API key. Sign in and replace it in VS Code.', status);
    }
    if (status === 403) {
      return new AChatApiError('AChat denied remote-agent access. Ask an admin to allow Remote Agents and the agent owner to grant Remote Access.', status);
    }
    if (status === 404) {
      return new AChatApiError('AChat API endpoint was not found. Check that the base URL points to your AChat server.', status);
    }
    if (status === 429) {
      return new AChatApiError('AChat rate limit reached. Wait briefly and try again.', status);
    }
    if (status >= 500) {
      return new AChatApiError(`AChat server error (${status}). Try again later.`, status);
    }

    let detail = '';
    try {
      const payload = await response.json() as { error?: { message?: unknown } | string; message?: unknown };
      const raw = typeof payload.error === 'string'
        ? payload.error
        : typeof payload.error?.message === 'string'
          ? payload.error.message
          : typeof payload.message === 'string'
            ? payload.message
            : '';
      detail = raw.replace(/[\r\n\t]+/g, ' ').slice(0, 180);
    } catch {
      // Ignore non-JSON error bodies.
    }
    return new AChatApiError(detail ? `AChat request failed (${status}): ${detail}` : `AChat request failed (${status}).`, status);
  }
}
