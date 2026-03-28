import type {
  AgentRun,
  AgentStatus,
  ChatMessage,
  ChatResponse,
  ComplianceReport,
  FinancialResult,
  OffsetMarket,
  OffsetPortfolioSummary,
  OffsetProject,
  OffsetPurchase,
  OffsetRecommendation,
  OffsetRegistry,
  ReductionSuggestion,
  Scenario,
  ScenarioInputPayload,
  TokenWithUser,
  UserOut,
} from '../types'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function buildPath(path: string): string {
  return `${API_ROOT}${path}`
}

function authHeaders(token?: string | null): Headers {
  const headers = new Headers()
  headers.set('Accept', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return headers
}

async function request<T>(path: string, init?: RequestInit, token?: string | null): Promise<T> {
  const headers = authHeaders(token)
  const providedHeaders = new Headers(init?.headers)

  providedHeaders.forEach((value, key) => {
    headers.set(key, value)
  })

  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(buildPath(path), {
    ...init,
    headers,
  })

  if (!response.ok) {
    let detail = response.statusText || 'Request failed'
    const contentType = response.headers.get('content-type') ?? ''

    try {
      if (contentType.includes('application/json')) {
        const payload = (await response.json()) as { detail?: string }
        detail = payload.detail ?? JSON.stringify(payload)
      } else {
        detail = (await response.text()) || detail
      }
    } catch {
      // fall back to status text
    }

    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return undefined as T

  return (await response.json()) as T
}

async function download(path: string, filename: string, token?: string | null): Promise<void> {
  const response = await fetch(buildPath(path), {
    headers: authHeaders(token),
  })

  if (!response.ok) {
    throw new ApiError('Download failed', response.status)
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const api = {
  login(email: string, password: string) {
    return request<TokenWithUser>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  register(email: string, password: string) {
    return request<TokenWithUser>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  me(token: string) {
    return request<UserOut>('/api/auth/me', undefined, token)
  },

  listScenarios(token: string) {
    return request<Scenario[]>('/api/scenarios', undefined, token)
  },

  getScenario(id: string, token: string) {
    return request<Scenario>(`/api/scenarios/${id}`, undefined, token)
  },

  createScenario(payload: ScenarioInputPayload, token: string) {
    return request<Scenario>('/api/scenarios', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, token)
  },

  updateScenario(id: string, payload: ScenarioInputPayload, token: string) {
    return request<Scenario>(`/api/scenarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }, token)
  },

  deleteScenario(id: string, token: string) {
    return request<{ deleted: string }>(`/api/scenarios/${id}`, {
      method: 'DELETE',
    }, token)
  },

  cloneScenario(id: string, name: string, token: string) {
    const params = new URLSearchParams({ name })
    return request<Scenario>(`/api/scenarios/${id}/clone?${params.toString()}`, {
      method: 'POST',
    }, token)
  },

  getScenarioSuggestions(id: string, token: string) {
    return request<ReductionSuggestion[]>(`/api/scenarios/${id}/suggestions?target_pct=30`, undefined, token)
  },

  exportScenario(id: string, token: string) {
    return request<Record<string, unknown>>(`/api/scenarios/${id}/export`, undefined, token)
  },

  sendChat(messages: ChatMessage[], eventContext: Record<string, unknown>, token: string, scenarioId?: string | null) {
    return request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        messages,
        event_context: eventContext,
        scenario_id: scenarioId ?? null,
      }),
    }, token)
  },

  calculateSavings(payload: Record<string, unknown>, token: string) {
    return request<FinancialResult>('/api/financial/savings', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, token)
  },

  checkCompliance(params: URLSearchParams) {
    return request<ComplianceReport>(`/api/financial/compliance?${params.toString()}`, {
      method: 'POST',
    })
  },

  listOffsetProjects() {
    return request<Record<string, OffsetProject>>('/api/offsets/projects')
  },

  listOffsetRegistries() {
    return request<Record<string, OffsetRegistry>>('/api/offsets/registries')
  },

  getOffsetMarket() {
    return request<OffsetMarket>('/api/offsets/market')
  },

  listOffsetPurchases(token: string) {
    return request<OffsetPurchase[]>('/api/offsets', undefined, token)
  },

  getOffsetPortfolio(token: string, scenarioId?: string | null) {
    const params = new URLSearchParams()
    if (scenarioId) params.set('scenario_id', scenarioId)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return request<OffsetPortfolioSummary>(`/api/offsets/portfolio${suffix}`, undefined, token)
  },

  createOffsetPurchase(payload: Record<string, unknown>, token: string) {
    return request<OffsetPurchase>('/api/offsets', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, token)
  },

  retireOffset(id: number, token: string) {
    return request<OffsetPurchase>(`/api/offsets/${id}/retire`, {
      method: 'POST',
    }, token)
  },

  cancelOffset(id: number, token: string) {
    return request<{ cancelled: number }>(`/api/offsets/${id}`, {
      method: 'DELETE',
    }, token)
  },

  getOffsetRecommendations(scenarioId: string, token: string) {
    return request<OffsetRecommendation[]>(`/api/offsets/recommend/${scenarioId}`, undefined, token)
  },

  getAgentStatus(token: string) {
    return request<AgentStatus[]>('/api/agents/status', undefined, token)
  },

  getAgentHistory(token: string) {
    return request<AgentRun[]>('/api/agents/history?limit=50', undefined, token)
  },

  runAgentsSync(token: string) {
    return request<Record<string, unknown>>('/api/agents/run/sync?force=true', undefined, token)
  },

  runAgentsForce(token: string) {
    return request<Record<string, unknown>>('/api/agents/run?force=true', {
      method: 'POST',
    }, token)
  },

  recalculateScenarios(token: string) {
    return request<{
      updated_count: number
      failed_count: number
      failures: Array<Record<string, unknown>>
      scenarios: Scenario[]
    }>('/api/scenarios/recalculate/all', {
      method: 'POST',
    }, token)
  },

  download(path: string, filename: string, token?: string | null) {
    return download(path, filename, token)
  },
}
