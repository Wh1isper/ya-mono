import type {
  ClawInfo,
  HealthStatus,
  InputPart,
  ProfileDetail,
  ProfileSeedResponse,
  ProfileSummary,
  ProfileUpsertRequest,
  RunDetail,
  RunGetResponse,
  RunTraceResponse,
  SessionCreateResponse,
  SessionGetResponse,
  SessionRunCreateRequest,
  SessionSummary,
} from '../types'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export type ApiClientConfig = {
  baseUrl: string
  apiToken: string
}

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/$/, '')
}

export class ClawApiClient {
  private readonly baseUrl: string
  private readonly apiToken: string

  constructor(config: ApiClientConfig) {
    this.baseUrl = normalizeBaseUrl(config.baseUrl)
    this.apiToken = config.apiToken
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (!headers.has('Content-Type') && init.body !== undefined) {
      headers.set('Content-Type', 'application/json')
    }
    if (this.apiToken.trim()) {
      headers.set('Authorization', `Bearer ${this.apiToken.trim()}`)
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    })

    if (!response.ok) {
      let detail: unknown = null
      try {
        detail = await response.json()
      } catch {
        detail = await response.text()
      }
      throw new ApiError(
        `Request failed with ${response.status}`,
        response.status,
        detail,
      )
    }

    if (response.status === 204) {
      return undefined as T
    }

    return (await response.json()) as T
  }

  health() {
    return this.request<HealthStatus>('/healthz')
  }

  clawInfo() {
    return this.request<ClawInfo>('/api/v1/claw/info')
  }

  listSessions() {
    return this.request<SessionSummary[]>('/api/v1/sessions')
  }

  getSession(sessionId: string) {
    return this.request<SessionGetResponse>(
      `/api/v1/sessions/${sessionId}?include_message=true&include_input_parts=true`,
    )
  }

  createSession(payload: {
    profile_name?: string | null
    input_parts: InputPart[]
    metadata?: Record<string, unknown>
  }) {
    return this.request<SessionCreateResponse>('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  createSessionRun(sessionId: string, payload: SessionRunCreateRequest) {
    return this.request<RunDetail>(`/api/v1/sessions/${sessionId}/runs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  getRun(runId: string) {
    return this.request<RunGetResponse>(
      `/api/v1/runs/${runId}?include_message=true`,
    )
  }

  getRunTrace(runId: string) {
    return this.request<RunTraceResponse>(`/api/v1/runs/${runId}/trace`)
  }

  steerRun(runId: string, inputParts: InputPart[]) {
    return this.request(`/api/v1/runs/${runId}/steer`, {
      method: 'POST',
      body: JSON.stringify({ input_parts: inputParts }),
    })
  }

  interruptRun(runId: string) {
    return this.request<RunDetail>(`/api/v1/runs/${runId}/interrupt`, {
      method: 'POST',
    })
  }

  cancelRun(runId: string) {
    return this.request<RunDetail>(`/api/v1/runs/${runId}/cancel`, {
      method: 'POST',
    })
  }

  listProfiles() {
    return this.request<ProfileSummary[]>('/api/v1/profiles')
  }

  getProfile(profileName: string) {
    return this.request<ProfileDetail>(
      `/api/v1/profiles/${encodeURIComponent(profileName)}`,
    )
  }

  upsertProfile(profileName: string, payload: ProfileUpsertRequest) {
    return this.request<ProfileDetail>(
      `/api/v1/profiles/${encodeURIComponent(profileName)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    )
  }

  deleteProfile(profileName: string) {
    return this.request<void>(
      `/api/v1/profiles/${encodeURIComponent(profileName)}`,
      {
        method: 'DELETE',
      },
    )
  }

  seedProfiles(pruneMissing: boolean) {
    return this.request<ProfileSeedResponse>('/api/v1/profiles/seed', {
      method: 'POST',
      body: JSON.stringify({ prune_missing: pruneMissing }),
    })
  }
}
