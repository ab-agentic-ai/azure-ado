export interface AChatAgent {
  id: string;
  name: string;
  description?: string;
  provider?: string;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  model: string;
  messages: ChatMessage[];
  stream: true;
}

export interface ChatUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
}

export interface ChatContextItem {
  id: string;
  path: string;
  kind: 'selection' | 'file';
  content: string;
  truncated?: boolean;
}

export interface ChatResult {
  finishReason?: string | null;
  usage?: ChatUsage;
}

export class AChatApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'AChatApiError';
  }
}
