export type DataEnvelope<T> = {
  data: T;
};

export type PaginationMeta = {
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
};

export type ListEnvelope<T> = {
  data: T[];
  meta: PaginationMeta;
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details: { field_errors: unknown[] };
  };
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type UserPublic = {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  email_verified_at: string | null;
  last_login_at: string | null;
  is_active: boolean;
};

export type ProjectOut = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  owner_user_id: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentDefinitionOut = {
  id: string;
  project_id: string;
  agent_id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  model: string;
  vault_key_id: string;
  tools_config: Record<string, unknown>;
  max_iterations: number;
  max_tokens_per_run: number;
  is_archived: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
};

/** File artifact attached to a run (Phase 7.2 receipt drawer). */
export type AgentRunArtifact = {
  path: string;
  url: string;
  content_type: string;
  size_bytes: number;
};

export type AgentRunOut = {
  id: string;
  project_id: string;
  agent_definition_id: string;
  status: string;
  correlation_id: string;
  input_payload: Record<string, unknown> | null;
  final_output: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  receipt_ids?: string[];
  artifacts?: AgentRunArtifact[];
};

export type AgentRunWsTokenPayload = {
  token: string;
  expires_in_seconds: number;
};
