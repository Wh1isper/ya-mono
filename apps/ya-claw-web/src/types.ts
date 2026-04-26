export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export type HealthStatus = {
  status: string
  database: string
  runtime_state: string
}

export type ClawInfo = {
  name: string
  environment: string
  version: string
  public_base_url: string
  instance_id: string
  auth: 'bearer'
  surfaces: string[]
  workspace_provider_backend: string
  storage_model: string
  features: {
    session_events: boolean
    run_events: boolean
    notifications: boolean
    profiles: boolean
  }
}

export type InputPart =
  | { type: 'text'; text: string; metadata?: Record<string, unknown> | null }
  | {
      type: 'url'
      url: string
      kind: string
      filename?: string | null
      storage?: 'ephemeral' | 'persistent' | 'inline'
      metadata?: Record<string, unknown> | null
    }
  | {
      type: 'file'
      path: string
      kind: string
      metadata?: Record<string, unknown> | null
    }
  | {
      type: 'binary'
      data: string
      mime_type: string
      kind: string
      filename?: string | null
      storage?: 'ephemeral' | 'persistent' | 'inline'
      metadata?: Record<string, unknown> | null
    }
  | {
      type: 'mode'
      mode: string
      params?: Record<string, unknown> | null
      metadata?: Record<string, unknown> | null
    }
  | {
      type: 'command'
      name: string
      params?: Record<string, unknown> | null
      metadata?: Record<string, unknown> | null
    }

export type RunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
export type SessionStatus = 'idle' | RunStatus

export type AguiEvent = Record<string, unknown> & {
  type?: string
  timestamp?: number
  messageId?: string
  message_id?: string
  role?: string
  name?: string
  delta?: string
  toolCallId?: string
  tool_call_id?: string
  toolCallName?: string
  tool_call_name?: string
  parentMessageId?: string
  parent_message_id?: string
  content?: unknown
  value?: unknown
  result?: unknown
  message?: string
  code?: string
}

export type RunSummary = {
  id: string
  session_id: string
  sequence_no: number
  restore_from_run_id?: string | null
  status: RunStatus
  trigger_type: string
  profile_name?: string | null
  input_preview?: string | null
  input_parts?: InputPart[] | null
  output_text?: string | null
  output_summary?: string | null
  error_message?: string | null
  termination_reason?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  committed_at?: string | null
  message?: AguiEvent[] | null
}

export type RunDetail = RunSummary & {
  metadata: Record<string, unknown>
  has_state: boolean
  has_message: boolean
}

export type SessionSummary = {
  id: string
  parent_session_id?: string | null
  profile_name?: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
  status: SessionStatus
  run_count: number
  head_run_id?: string | null
  head_success_run_id?: string | null
  active_run_id?: string | null
  latest_run?: RunSummary | null
}

export type SessionDetail = SessionSummary & {
  runs: RunSummary[]
  runs_limit: number
  runs_has_more: boolean
  runs_next_before_sequence_no?: number | null
}

export type SessionGetResponse = {
  session: SessionDetail
  state?: Record<string, unknown> | null
  message?: AguiEvent[] | null
}

export type SessionCreateResponse = {
  session: SessionSummary
  run?: RunDetail | null
}

export type SessionRunCreateRequest = {
  restore_from_run_id?: string | null
  reset_state?: boolean
  input_parts: InputPart[]
  metadata?: Record<string, unknown>
}

export type RunGetResponse = {
  session: SessionSummary
  run: RunDetail
  state?: Record<string, unknown> | null
  message?: AguiEvent[] | null
}

export type RunTraceItem = {
  sequence_no: number
  type: 'tool_call' | 'tool_response'
  tool_call_id?: string | null
  tool_name?: string | null
  message_id?: string | null
  role?: string | null
  content?: string | null
  truncated: boolean
}

export type RunTraceResponse = {
  run_id: string
  session_id: string
  item_count: number
  max_item_chars: number
  max_total_chars: number
  truncated: boolean
  trace: RunTraceItem[]
}

export type ProfileSubagent = {
  name: string
  description: string
  system_prompt: string
  model?: string | null
  model_settings_preset?: string | null
  model_settings_override?: Record<string, unknown> | null
  model_config_preset?: string | null
  model_config_override?: Record<string, unknown> | null
}

export type ProfileMCPServer = {
  transport: 'streamable_http'
  url: string
  headers: Record<string, string>
  description: string
  required: boolean
}

export type ProfileSummary = {
  name: string
  model: string
  workspace_backend_hint?: string | null
  enabled: boolean
  source_type?: string | null
  source_version?: string | null
  updated_at: string
}

export type ProfileDetail = ProfileSummary & {
  model_settings_preset?: string | null
  model_settings_override?: Record<string, unknown> | null
  model_config_preset?: string | null
  model_config_override?: Record<string, unknown> | null
  system_prompt?: string | null
  builtin_toolsets: string[]
  toolsets: string[]
  subagents: ProfileSubagent[]
  include_builtin_subagents: boolean
  unified_subagents: boolean
  need_user_approve_tools: string[]
  need_user_approve_mcps: string[]
  enabled_mcps: string[]
  disabled_mcps: string[]
  mcp_servers: Record<string, ProfileMCPServer>
  source_checksum?: string | null
  created_at: string
}

export type ProfileUpsertRequest = {
  model: string
  model_settings_preset?: string | null
  model_settings_override?: Record<string, unknown> | null
  model_config_preset?: string | null
  model_config_override?: Record<string, unknown> | null
  system_prompt?: string | null
  builtin_toolsets: string[]
  subagents: ProfileSubagent[]
  include_builtin_subagents: boolean
  unified_subagents: boolean
  need_user_approve_tools: string[]
  need_user_approve_mcps: string[]
  enabled_mcps: string[]
  disabled_mcps: string[]
  mcp_servers: Record<string, ProfileMCPServer>
  workspace_backend_hint?: string | null
  enabled: boolean
  source_type?: string | null
  source_version?: string | null
  source_checksum?: string | null
}

export type ProfileSeedResponse = {
  seeded_names: string[]
  seed_file: string
  prune_missing: boolean
}

export type NotificationEvent = {
  id: string
  type: string
  created_at: string
  payload: Record<string, unknown>
}
