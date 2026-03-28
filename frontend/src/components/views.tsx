import { type Dispatch, type FormEvent, type SetStateAction, useDeferredValue, useState } from 'react'
import {
  ACCOMMODATION_OPTIONS,
  AVAILABLE_ACTIONS,
  CATERING_OPTIONS,
  EVENT_TYPES,
  FINANCIAL_REGIONS,
  GRID_OPTIONS,
  START_SUGGESTIONS,
  TRAVEL_CLASS_OPTIONS,
  TRAVEL_MODE_OPTIONS,
  TSHIRT_OPTIONS,
} from '../lib/constants'
import {
  cn,
  formatCurrency,
  formatDateTime,
  formatKgPerAttendee,
  formatTons,
  labelize,
} from '../lib/format'
import type {
  AgentRun,
  AgentStatus,
  AuthMode,
  ChatMessage,
  ComplianceInput,
  ComplianceReport,
  FinancialCalcState,
  FinancialResult,
  NewOffsetPurchase,
  OffsetMarket,
  OffsetPortfolioSummary,
  OffsetProject,
  OffsetPurchase,
  OffsetRecommendation,
  OffsetRegistry,
  ReductionSuggestion,
  Scenario,
  ScenarioDraft,
} from '../types'
import { Badge, Button, EmptyState, Glyph, Panel } from './primitives'

interface AuthViewProps {
  mode: AuthMode
  email: string
  password: string
  error: string
  busy: boolean
  onModeChange: (mode: AuthMode) => void
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => void
}

export function AuthView({
  mode,
  email,
  password,
  error,
  busy,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: AuthViewProps) {
  return (
    <div className="auth-shell">
      <div className="auth-poster">
        <span className="eyebrow">CutCarbon Co-Pilot</span>
        <h1>Transition the carbon workspace from rough estimates to operating reality.</h1>
        <p>
          Model event scenarios, price reductions, audit factor freshness, and keep one live
          workspace for sustainability, finance, and compliance.
        </p>
        <div className="auth-poster-grid">
          <article>
            <span>Scenarios</span>
            <strong>What-if modeling</strong>
          </article>
          <article>
            <span>Finance</span>
            <strong>Tax and incentive upside</strong>
          </article>
          <article>
            <span>Agents</span>
            <strong>Live factor refresh</strong>
          </article>
        </div>
      </div>
      <Panel className="auth-panel">
        <div className="auth-panel-head">
          <img className="app-logo" src="/favicon.svg" alt="CutCarbon logo" />
          <div>
            <strong>Welcome back</strong>
            <p>Use your workspace credentials to access your carbon workspace.</p>
          </div>
        </div>
        <div className="toggle-row">
          <button
            type="button"
            className={mode === 'login' ? 'toggle-pill is-active' : 'toggle-pill'}
            onClick={() => onModeChange('login')}
          >
            Sign in
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'toggle-pill is-active' : 'toggle-pill'}
            onClick={() => onModeChange('register')}
          >
            Register
          </button>
        </div>
        <label className="field">
          <span>Email</span>
          <input value={email} onChange={(event) => onEmailChange(event.target.value)} placeholder="you@example.com" />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            placeholder="••••••••"
            type="password"
          />
        </label>
        {error ? <p className="field-error">{error}</p> : null}
        <Button tone="primary" busy={busy} onClick={onSubmit}>
          {mode === 'login' ? 'Enter workspace' : 'Create account'}
        </Button>
      </Panel>
    </div>
  )
}

interface ChatViewProps {
  messages: ChatMessage[]
  chatInput: string
  chatLoading: boolean
  selectedScenario: Scenario | null
  onChatInputChange: (value: string) => void
  onSend: () => void
  onApplyExtracted: (data: Record<string, unknown>) => void
  onUseSuggestion: (prompt: string) => void
}

export function ChatView({
  messages,
  chatInput,
  chatLoading,
  selectedScenario,
  onChatInputChange,
  onSend,
  onApplyExtracted,
  onUseSuggestion,
}: ChatViewProps) {
  return (
    <div className="split-view">
      <Panel className="chat-thread">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Conversation</span>
            <h3>AI co-pilot</h3>
          </div>
        </div>

        {!messages.length ? (
          <div className="chat-empty">
            <Glyph label="AI" tone="cyan" />
            <h3>Describe your event</h3>
            <div className="prompt-grid">
              {START_SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} className="prompt-chip" onClick={() => onUseSuggestion(suggestion)} type="button">
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-list">
            {messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={message.role === 'user' ? 'message-bubble user' : 'message-bubble assistant'}>
                <div className="message-copy">
                  <span>{message.content}</span>
                </div>
                {message.extracted_data && Object.keys(message.extracted_data).length ? (
                  <div className="extracted-box">
                    <Button tone="soft" onClick={() => onApplyExtracted(message.extracted_data ?? {})}>
                      Apply to scenario
                    </Button>
                  </div>
                ) : null}
              </article>
            ))}
            {chatLoading ? <div className="typing-row">Drafting…</div> : null}
          </div>
        )}

        <div className="chat-composer">
          <textarea
            value={chatInput}
            onChange={(event) => onChatInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                onSend()
              }
            }}
            placeholder="Describe the event, ask for reduction ideas, or request financial analysis…"
            rows={3}
          />
          <Button tone="primary" busy={chatLoading} onClick={onSend}>
            Send
          </Button>
        </div>
      </Panel>

      <div className="stacked-panels">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Active scenario</span>
              <h3>Context</h3>
            </div>
          </div>
          {selectedScenario ? (
            <div className="signal-grid">
              <article className="signal-card">
                <span className="eyebrow">{selectedScenario.location}</span>
                <strong>{selectedScenario.name}</strong>
              </article>
              <article className="signal-card">
                <span className="eyebrow">Footprint</span>
                <strong>{formatTons(selectedScenario.emissions.total_tco2e)}</strong>
                <p>{formatKgPerAttendee(selectedScenario.emissions.per_attendee_tco2e)} per attendee</p>
              </article>
            </div>
          ) : (
            <EmptyState title="No scenario selected" body="Create a scenario to give the co-pilot context." />
          )}
        </Panel>
      </div>
    </div>
  )
}

interface ScenariosViewProps {
  draft: ScenarioDraft
  setDraft: Dispatch<SetStateAction<ScenarioDraft>>
  scenarioLoading: boolean
  editingScenario: Scenario | null
  scenarios: Scenario[]
  selectedScenario: Scenario | null
  suggestions: ReductionSuggestion[]
  onSubmit: () => void
  onCancelEdit: () => void
  onEdit: (scenario: Scenario) => void
  onClone: (scenario: Scenario) => void
  onDelete: (id: string) => void
  onExport: (scenario: Scenario) => void
  onSelectScenario: (scenario: Scenario) => void
  onLoadSuggestions: (scenario: Scenario) => void
}

export function ScenariosView({
  draft,
  setDraft,
  scenarioLoading,
  editingScenario,
  scenarios,
  selectedScenario,
  suggestions,
  onSubmit,
  onCancelEdit,
  onEdit,
  onClone,
  onDelete,
  onExport,
  onSelectScenario,
  onLoadSuggestions,
}: ScenariosViewProps) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const filteredScenarios = scenarios.filter((scenario) =>
    `${scenario.name} ${scenario.location} ${scenario.event_type}`.toLowerCase().includes(deferredQuery.toLowerCase()),
  )

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <div className="split-view split-view-forms">
      <Panel className="scenario-form-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Scenario builder</span>
            <h3>{editingScenario ? 'Update active scenario' : 'Create a new scenario'}</h3>
          </div>
          {editingScenario ? <Badge tone="amber">Editing {editingScenario.name}</Badge> : null}
        </div>

        <form className="scenario-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field">
              <span>Scenario name</span>
              <input
                value={draft.name}
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                placeholder="APAC Summit baseline"
              />
            </label>
            <label className="field">
              <span>Event type</span>
              <select
                value={draft.event_type}
                onChange={(event) => setDraft((current) => ({ ...current, event_type: event.target.value }))}
              >
                {EVENT_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Attendees</span>
              <input
                type="number"
                value={draft.attendees}
                onChange={(event) => setDraft((current) => ({ ...current, attendees: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Event days</span>
              <input
                type="number"
                value={draft.event_days}
                onChange={(event) => setDraft((current) => ({ ...current, event_days: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Location</span>
              <input
                value={draft.location}
                onChange={(event) => setDraft((current) => ({ ...current, location: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Grid region</span>
              <select
                value={draft.venue_grid}
                onChange={(event) => setDraft((current) => ({ ...current, venue_grid: event.target.value }))}
              >
                {GRID_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Catering</span>
              <select
                value={draft.catering_type}
                onChange={(event) => setDraft((current) => ({ ...current, catering_type: event.target.value }))}
              >
                {CATERING_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Accommodation</span>
              <select
                value={draft.accommodation_type}
                onChange={(event) => setDraft((current) => ({ ...current, accommodation_type: event.target.value }))}
              >
                {ACCOMMODATION_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="slider-field">
            <span>Renewable energy mix</span>
            <div className="slider-line">
              <input
                type="range"
                min={0}
                max={100}
                value={draft.renewable_pct}
                onChange={(event) => setDraft((current) => ({ ...current, renewable_pct: Number(event.target.value) }))}
              />
              <strong>{draft.renewable_pct}%</strong>
            </div>
          </label>

          <label className="check-field">
            <input
              checked={draft.include_alcohol}
              onChange={(event) => setDraft((current) => ({ ...current, include_alcohol: event.target.checked }))}
              type="checkbox"
            />
            <span>Include alcohol service</span>
          </label>

          <div className="subpanel">
            <div className="subpanel-header">
              <div>
                <span className="eyebrow">Travel segments</span>
                <h4>Travel assumptions</h4>
              </div>
              <Button
                tone="soft"
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    travel_segments: [
                      ...current.travel_segments,
                      {
                        mode: 'long_haul_flight',
                        travel_class: 'economy',
                        attendees: 100,
                        distance_km: 2000,
                        label: '',
                      },
                    ],
                  }))
                }
                type="button"
              >
                Add segment
              </Button>
            </div>
            <div className="travel-list">
              {draft.travel_segments.length ? (
                draft.travel_segments.map((segment, index) => (
                  <div key={`${segment.mode}-${index}`} className="travel-row">
                    <select
                      value={segment.mode}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          travel_segments: current.travel_segments.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, mode: event.target.value } : item,
                          ),
                        }))
                      }
                    >
                      {TRAVEL_MODE_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <select
                      value={segment.travel_class}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          travel_segments: current.travel_segments.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, travel_class: event.target.value } : item,
                          ),
                        }))
                      }
                    >
                      {TRAVEL_CLASS_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={segment.attendees}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          travel_segments: current.travel_segments.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, attendees: Number(event.target.value) } : item,
                          ),
                        }))
                      }
                    />
                    <input
                      type="number"
                      value={segment.distance_km}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          travel_segments: current.travel_segments.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, distance_km: Number(event.target.value) } : item,
                          ),
                        }))
                      }
                    />
                    <button
                      className="mini-action danger"
                      onClick={() =>
                        setDraft((current) => ({
                          ...current,
                          travel_segments: current.travel_segments.filter((_, itemIndex) => itemIndex !== index),
                        }))
                      }
                      type="button"
                    >
                      Remove
                    </button>
                  </div>
                ))
              ) : (
                <p className="subtle-copy">No travel segments yet. Add one for more realistic footprint estimates.</p>
              )}
            </div>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Stage area (m²)</span>
              <input
                type="number"
                value={draft.stage_m2}
                onChange={(event) => setDraft((current) => ({ ...current, stage_m2: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Lighting days</span>
              <input
                type="number"
                value={draft.lighting_days}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, lighting_days: Number(event.target.value) }))
                }
              />
            </label>
            <label className="field">
              <span>Sound system days</span>
              <input
                type="number"
                value={draft.sound_system_days}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, sound_system_days: Number(event.target.value) }))
                }
              />
            </label>
            <label className="field">
              <span>LED screen area (m²)</span>
              <input
                type="number"
                value={draft.led_screen_m2}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, led_screen_m2: Number(event.target.value) }))
                }
              />
            </label>
            <label className="field">
              <span>Generator hours</span>
              <input
                type="number"
                value={draft.generator_hours}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, generator_hours: Number(event.target.value) }))
                }
              />
            </label>
            <label className="field">
              <span>T-shirt type</span>
              <select
                value={draft.tshirt_type}
                onChange={(event) => setDraft((current) => ({ ...current, tshirt_type: event.target.value }))}
              >
                {TSHIRT_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>T-shirts</span>
              <input
                type="number"
                value={draft.tshirts}
                onChange={(event) => setDraft((current) => ({ ...current, tshirts: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Tote bags</span>
              <input
                type="number"
                value={draft.tote_bags}
                onChange={(event) => setDraft((current) => ({ ...current, tote_bags: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Lanyards</span>
              <input
                type="number"
                value={draft.lanyards}
                onChange={(event) => setDraft((current) => ({ ...current, lanyards: Number(event.target.value) }))}
              />
            </label>
            <label className="field">
              <span>Badges</span>
              <input
                type="number"
                value={draft.badges}
                onChange={(event) => setDraft((current) => ({ ...current, badges: Number(event.target.value) }))}
              />
            </label>
          </div>

          <div className="hero-actions">
            <Button tone="primary" busy={scenarioLoading} type="submit">
              {editingScenario ? 'Update scenario' : 'Calculate scenario'}
            </Button>
            {editingScenario ? (
              <Button tone="ghost" onClick={onCancelEdit} type="button">
                Cancel edit
              </Button>
            ) : null}
          </div>
        </form>
      </Panel>

      <div className="stacked-panels">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Scenario library</span>
              <h3>Saved scenarios</h3>
            </div>
            <input
              className="search-input"
              placeholder="Search scenarios"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          {filteredScenarios.length ? (
            <div className="scenario-list">
              {filteredScenarios.map((scenario) => (
                <article
                  key={scenario.scenario_id}
                  className={cn(
                    'scenario-card',
                    selectedScenario?.scenario_id === scenario.scenario_id && 'is-selected',
                  )}
                >
                  <button className="scenario-card-main" onClick={() => onSelectScenario(scenario)} type="button">
                    <div className="scenario-card-top">
                      <div>
                        <strong>{scenario.name}</strong>
                        <p>
                          {scenario.location} · {labelize(scenario.event_type)} · {scenario.attendees} attendees
                        </p>
                      </div>
                      <div className="scenario-card-metric">
                        <strong>{formatTons(scenario.emissions.total_tco2e)}</strong>
                        <span>{formatKgPerAttendee(scenario.emissions.per_attendee_tco2e)} / attendee</span>
                      </div>
                    </div>
                    <div className="scenario-progress-list">
                      {[
                        ['Travel', scenario.emissions.travel_tco2e, 'var(--accent-lake)'],
                        ['Energy', scenario.emissions.venue_energy_tco2e, 'var(--accent-fresh)'],
                        ['Catering', scenario.emissions.catering_tco2e, 'var(--accent-amber)'],
                      ].map(([label, value, color]) => (
                        <div key={label} className="scenario-progress-row">
                          <span>{label}</span>
                          <div className="scenario-progress-bar">
                            <span
                              style={{
                                width: `${scenario.emissions.total_tco2e ? (Number(value) / scenario.emissions.total_tco2e) * 100 : 0}%`,
                                background: String(color),
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </button>
                  <div className="scenario-card-actions">
                    <Button tone="soft" onClick={() => onEdit(scenario)} type="button">
                      Edit
                    </Button>
                    <Button tone="soft" onClick={() => onClone(scenario)} type="button">
                      Clone
                    </Button>
                    <Button tone="soft" onClick={() => onLoadSuggestions(scenario)} type="button">
                      Reduce
                    </Button>
                    <Button tone="soft" onClick={() => onExport(scenario)} type="button">
                      Export
                    </Button>
                    <Button tone="danger" onClick={() => onDelete(scenario.scenario_id)} type="button">
                      Delete
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No scenarios found" body="Create a baseline or clear the search query to see everything again." />
          )}
        </Panel>

        {suggestions.length ? (
          <Panel>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Suggestions</span>
                <h3>Reduction actions for the selected scenario</h3>
              </div>
              <Badge tone="amber">Target -30%</Badge>
            </div>
            <div className="suggestion-grid">
              {suggestions.map((suggestion) => (
                <article key={suggestion.action} className="suggestion-card">
                  <div className="suggestion-meta">
                    <Badge tone={suggestion.difficulty === 'easy' ? 'fresh' : suggestion.difficulty === 'medium' ? 'amber' : 'rose'}>
                      {suggestion.difficulty}
                    </Badge>
                    <span>{suggestion.category}</span>
                  </div>
                  <strong>{suggestion.label}</strong>
                  <div className="suggestion-metrics">
                    <span>{formatTons(suggestion.co2e_saved_tco2e, 3)}</span>
                    <span>
                      {suggestion.estimated_cost_usd < 0
                        ? `Saves ${formatCurrency(Math.abs(suggestion.estimated_cost_usd))}`
                        : `+${formatCurrency(suggestion.estimated_cost_usd)}`}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </Panel>
        ) : null}
      </div>
    </div>
  )
}

interface FinancialViewProps {
  calc: FinancialCalcState
  setCalc: Dispatch<SetStateAction<FinancialCalcState>>
  result: FinancialResult | null
  loading: boolean
  scenarios: Scenario[]
  selectedScenario: Scenario | null
  onCalculate: () => void
}

export function FinancialView({
  calc,
  setCalc,
  result,
  loading,
  scenarios,
  selectedScenario,
  onCalculate,
}: FinancialViewProps) {
  return (
    <div className="split-view split-view-forms">
      <Panel className="input-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Financial lens</span>
            <h3>Savings calculator</h3>
          </div>
          {calc.linked_scenario_name ? <Badge tone="fresh">Linked to {calc.linked_scenario_name}</Badge> : null}
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Linked scenario</span>
            <select
              value={calc.linked_scenario_id ?? ''}
              onChange={(event) => {
                const nextId = event.target.value || null
                const nextScenario = scenarios.find((scenario) => scenario.scenario_id === nextId) ?? null
                setCalc((current) => ({
                  ...current,
                  linked_scenario_id: nextScenario?.scenario_id ?? null,
                  linked_scenario_name: nextScenario?.name ?? null,
                }))
              }}
            >
              <option value="">General calculator</option>
              {scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Region</span>
            <select
              value={calc.region}
              onChange={(event) => setCalc((current) => ({ ...current, region: event.target.value }))}
            >
              {FINANCIAL_REGIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Baseline emissions</span>
            <input
              type="number"
              value={calc.baseline}
              onChange={(event) => setCalc((current) => ({ ...current, baseline: Number(event.target.value) }))}
            />
          </label>

          <label className="slider-field">
            <span>Target reduction</span>
            <div className="slider-line">
              <input
                type="range"
                min={5}
                max={95}
                value={calc.reduction_pct}
                onChange={(event) => setCalc((current) => ({ ...current, reduction_pct: Number(event.target.value) }))}
              />
              <strong>{calc.reduction_pct}%</strong>
            </div>
          </label>

          <label className="field">
            <span>Energy saved (kWh)</span>
            <input
              type="number"
              value={calc.energy_kwh}
              onChange={(event) => setCalc((current) => ({ ...current, energy_kwh: Number(event.target.value) }))}
            />
          </label>

          <label className="field">
            <span>Meal switches</span>
            <input
              type="number"
              value={calc.meal_switches}
              onChange={(event) => setCalc((current) => ({ ...current, meal_switches: Number(event.target.value) }))}
            />
          </label>
        </div>

        <div className="check-grid">
          {AVAILABLE_ACTIONS.map((action) => (
            <label key={action.key} className="check-field">
              <input
                checked={calc.actions.includes(action.key)}
                onChange={(event) =>
                  setCalc((current) => ({
                    ...current,
                    actions: event.target.checked
                      ? [...current.actions, action.key]
                      : current.actions.filter((item) => item !== action.key),
                  }))
                }
                type="checkbox"
              />
              <span>{action.label}</span>
            </label>
          ))}
        </div>

        <div className="hero-actions">
          <Button tone="primary" busy={loading} onClick={onCalculate}>
            Calculate financial upside
          </Button>
          {selectedScenario ? <p className="subtle-copy">Selected scenario: {selectedScenario.name}</p> : null}
        </div>
      </Panel>

      <div className="stacked-panels">
        {result ? (
          <>
            <Panel className="highlight-panel">
              <span className="eyebrow">Total financial benefit</span>
              <strong>{formatCurrency(result.total_financial_savings_usd)}</strong>
              <p>
                {formatTons(result.total_co2e_reduced)} reduced · {result.co2e_reduction_pct.toFixed(1)}% cut
              </p>
            </Panel>
            <Panel>
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Tax savings</span>
                  <h3>Jurisdictional savings</h3>
                </div>
              </div>
              <div className="stack-list">
                {result.carbon_tax_savings.map((saving) => (
                  <article key={saving.scheme} className="stack-row">
                    <div>
                      <strong>{saving.scheme}</strong>
                      <p>{saving.description}</p>
                    </div>
                    <strong>{formatCurrency(saving.savings_usd)}</strong>
                  </article>
                ))}
              </div>
            </Panel>
            <Panel>
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Incentives</span>
                  <h3>Matched programs</h3>
                </div>
              </div>
              <div className="stack-list">
                {result.available_incentives.length ? (
                  result.available_incentives.map((incentive, index) => (
                    <article key={`${String(incentive.name ?? 'incentive')}-${index}`} className="stack-row">
                      <div>
                        <strong>{String(incentive.name ?? 'Incentive')}</strong>
                        <p>{String(incentive.benefit ?? incentive.type ?? 'Program detail')}</p>
                      </div>
                      <Badge tone="cyan">{String(incentive.type ?? 'program')}</Badge>
                    </article>
                  ))
                ) : (
                  <p className="subtle-copy">No incentives returned for this configuration.</p>
                )}
              </div>
            </Panel>
          </>
        ) : (
          <EmptyState
            title="No financial report yet"
            body="Run the calculator to translate modeled emissions cuts into savings and incentive value."
            className="compact-empty-state"
          />
        )}
      </div>
    </div>
  )
}

interface OffsetsViewProps {
  selectedScenario: Scenario | null
  projects: Record<string, OffsetProject>
  registries: Record<string, OffsetRegistry>
  market: OffsetMarket | null
  purchases: OffsetPurchase[]
  portfolio: OffsetPortfolioSummary | null
  recommendations: OffsetRecommendation[]
  draft: NewOffsetPurchase
  setDraft: Dispatch<SetStateAction<NewOffsetPurchase>>
  loading: boolean
  onCreate: () => void
  onRetire: (id: number) => void
  onCancel: (id: number) => void
  onLoadRecommendations: () => void
}

export function OffsetsView({
  selectedScenario,
  projects,
  registries,
  market,
  purchases,
  portfolio,
  recommendations,
  draft,
  setDraft,
  loading,
  onCreate,
  onRetire,
  onCancel,
  onLoadRecommendations,
}: OffsetsViewProps) {
  const registryOptions = Object.entries(registries)
  const projectOptions = Object.entries(projects)
  const selectedProject = projects[draft.project_type]

  return (
    <div className="split-view">
      <Panel>
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Offset portfolio</span>
            <h3>Purchase and retire credits</h3>
          </div>
          {selectedScenario ? <Badge tone="fresh">Linked scenario: {selectedScenario.name}</Badge> : null}
        </div>

        <div className="form-grid">
          <label className="field">
            <span>Project type</span>
            <select
              value={draft.project_type}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  project_type: event.target.value,
                  price_per_tco2e_usd: projects[event.target.value]?.avg_price_usd ?? current.price_per_tco2e_usd,
                }))
              }
            >
              {projectOptions.map(([value, project]) => (
                <option key={value} value={value}>
                  {project.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Registry</span>
            <select
              value={draft.registry}
              onChange={(event) => setDraft((current) => ({ ...current, registry: event.target.value }))}
            >
              {registryOptions.map(([value, registry]) => (
                <option key={value} value={value}>
                  {registry.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Quantity (tCO2e)</span>
            <input
              type="number"
              value={draft.quantity_tco2e}
              onChange={(event) =>
                setDraft((current) => ({ ...current, quantity_tco2e: Number(event.target.value) }))
              }
            />
          </label>
          <label className="field">
            <span>Price per tCO2e</span>
            <input
              type="number"
              value={draft.price_per_tco2e_usd}
              onChange={(event) =>
                setDraft((current) => ({ ...current, price_per_tco2e_usd: Number(event.target.value) }))
              }
            />
          </label>
          <label className="field">
            <span>Vintage year</span>
            <input
              type="number"
              value={draft.vintage_year}
              onChange={(event) => setDraft((current) => ({ ...current, vintage_year: Number(event.target.value) }))}
            />
          </label>
          <label className="field field-full">
            <span>Notes</span>
            <textarea
              rows={3}
              value={draft.notes}
              onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
            />
          </label>
        </div>

        {selectedProject ? (
          <div className="subpanel">
            <div className="subpanel-header">
              <div>
                <span className="eyebrow">Selected project</span>
                <h4>{selectedProject.label}</h4>
              </div>
              <Badge tone="cyan">{selectedProject.additionality_risk} risk</Badge>
            </div>
            <p className="subtle-copy">{selectedProject.description}</p>
            <div className="tag-row">
              {selectedProject.co_benefits.map((benefit) => (
                <Badge key={benefit} tone="neutral">
                  {benefit}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        <div className="hero-actions">
          <Button tone="primary" busy={loading} onClick={onCreate}>
            Record purchase
          </Button>
          <Button tone="soft" onClick={onLoadRecommendations}>
            Build recommendation mix
          </Button>
        </div>
      </Panel>

      <div className="stacked-panels">
        {portfolio ? (
          <Panel>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Portfolio summary</span>
                <h3>Coverage and spend</h3>
              </div>
            </div>
            <div className="metric-grid">
              <div className="mini-metric">
                <span>Purchased</span>
                <strong>{formatTons(portfolio.total_purchased_tco2e)}</strong>
              </div>
              <div className="mini-metric">
                <span>Retired</span>
                <strong>{formatTons(portfolio.total_retired_tco2e)}</strong>
              </div>
              <div className="mini-metric">
                <span>Total spend</span>
                <strong>{formatCurrency(portfolio.total_cost_usd)}</strong>
              </div>
              <div className="mini-metric">
                <span>Coverage</span>
                <strong>{portfolio.coverage_pct ? `${portfolio.coverage_pct}%` : '—'}</strong>
              </div>
            </div>
          </Panel>
        ) : null}

        {recommendations.length ? (
          <Panel>
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Recommended mix</span>
                <h3>Residual offset portfolio</h3>
              </div>
            </div>
            <div className="stack-list">
              {recommendations.map((recommendation) => (
                <article key={recommendation.project_type} className="stack-row">
                  <div>
                    <strong>{recommendation.label}</strong>
                    <p>{recommendation.description}</p>
                  </div>
                  <div className="stack-row-side">
                    <strong>{formatTons(recommendation.recommended_qty_tco2e)}</strong>
                    <span>{formatCurrency(recommendation.estimated_cost_usd)}</span>
                  </div>
                </article>
              ))}
            </div>
          </Panel>
        ) : null}

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Purchases</span>
              <h3>Credit activity</h3>
            </div>
            {market ? <Badge tone="amber">VCM avg {formatCurrency(Number(market.average_price_2024_usd ?? 0))}</Badge> : null}
          </div>
          <div className="stack-list">
            {purchases.length ? (
              purchases.map((purchase) => (
                <article key={purchase.id} className="stack-row">
                  <div>
                    <strong>{labelize(purchase.project_type)}</strong>
                    <p>
                      {purchase.quantity_tco2e} tCO2e · {purchase.registry} · {formatDateTime(purchase.created_at)}
                    </p>
                  </div>
                  <div className="stack-row-actions">
                    <Badge tone={purchase.status === 'retired' ? 'fresh' : purchase.status === 'cancelled' ? 'rose' : 'amber'}>
                      {purchase.status}
                    </Badge>
                    <strong>{formatCurrency(purchase.total_cost_usd)}</strong>
                    {purchase.status === 'purchased' ? (
                      <>
                        <Button tone="soft" onClick={() => onRetire(purchase.id)}>
                          Retire
                        </Button>
                        <Button tone="danger" onClick={() => onCancel(purchase.id)}>
                          Cancel
                        </Button>
                      </>
                    ) : null}
                  </div>
                </article>
              ))
            ) : (
              <p className="subtle-copy">No purchases recorded yet.</p>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}

interface ComplianceViewProps {
  input: ComplianceInput
  setInput: Dispatch<SetStateAction<ComplianceInput>>
  report: ComplianceReport | null
  loading: boolean
  scenarios: Scenario[]
  selectedScenario: Scenario | null
  onCheck: () => void
}

export function ComplianceView({
  input,
  setInput,
  report,
  loading,
  scenarios,
  selectedScenario,
  onCheck,
}: ComplianceViewProps) {
  return (
    <div className="split-view split-view-forms">
      <Panel className="input-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Compliance</span>
            <h3>Disclosure readiness</h3>
          </div>
          {selectedScenario ? <Badge tone="fresh">Selected {selectedScenario.name}</Badge> : null}
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Linked scenario</span>
            <select
              value={selectedScenario?.scenario_id ?? ''}
              onChange={(event) => {
                const nextId = event.target.value
                const nextScenario = scenarios.find((scenario) => scenario.scenario_id === nextId) ?? null
                if (nextScenario) {
                  setInput((current) => ({
                    ...current,
                    total_tco2e: nextScenario.emissions.total_tco2e,
                    attendees: nextScenario.attendees,
                    event_days: nextScenario.event_days,
                  }))
                }
              }}
            >
              <option value="">General checker</option>
              {scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Region</span>
            <select
              value={input.region}
              onChange={(event) => setInput((current) => ({ ...current, region: event.target.value }))}
            >
              {FINANCIAL_REGIONS.slice(0, 5).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Total tCO2e</span>
            <input
              type="number"
              value={input.total_tco2e}
              onChange={(event) => setInput((current) => ({ ...current, total_tco2e: Number(event.target.value) }))}
            />
          </label>
          <label className="field">
            <span>Attendees</span>
            <input
              type="number"
              value={input.attendees}
              onChange={(event) => setInput((current) => ({ ...current, attendees: Number(event.target.value) }))}
            />
          </label>
          <label className="field">
            <span>Event days</span>
            <input
              type="number"
              value={input.event_days}
              onChange={(event) => setInput((current) => ({ ...current, event_days: Number(event.target.value) }))}
            />
          </label>
        </div>
        <div className="check-grid">
          <label className="check-field">
            <input
              checked={input.has_scope3}
              onChange={(event) => setInput((current) => ({ ...current, has_scope3: event.target.checked }))}
              type="checkbox"
            />
            <span>Scope 3 included</span>
          </label>
          <label className="check-field">
            <input
              checked={input.has_ghg_report}
              onChange={(event) => setInput((current) => ({ ...current, has_ghg_report: event.target.checked }))}
              type="checkbox"
            />
            <span>GHG report drafted</span>
          </label>
        </div>
        <Button tone="primary" busy={loading} onClick={onCheck}>
          Run compliance check
        </Button>
      </Panel>

      <div className="stacked-panels">
        {report ? (
          <>
            <Panel className="highlight-panel">
              <span className="eyebrow">Overall score</span>
              <strong>{report.overall_score_pct.toFixed(0)}%</strong>
              <p>
                {report.penalty_risk_usd > 0
                  ? `Penalty risk ${formatCurrency(report.penalty_risk_usd)}`
                  : 'No penalty risk modeled right now.'}
              </p>
            </Panel>
            <Panel>
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Framework status</span>
                  <h3>Framework checks</h3>
                </div>
              </div>
              <div className="stack-list">
                {report.checks.map((check) => (
                  <article key={check.framework} className="framework-card">
                    <div className="framework-header">
                      <strong>{check.framework}</strong>
                      <Badge tone={check.status === 'compliant' ? 'fresh' : check.status === 'partial' ? 'amber' : check.status === 'not_applicable' ? 'neutral' : 'rose'}>
                        {labelize(check.status)}
                      </Badge>
                    </div>
                    <div className="framework-score">
                      <span style={{ width: `${check.score_pct}%` }} />
                    </div>
                    {check.gaps.length ? (
                      <div className="framework-list">
                        <strong>Gaps</strong>
                        {check.gaps.map((gap) => (
                          <p key={gap}>{gap}</p>
                        ))}
                      </div>
                    ) : null}
                    {check.recommendations.length ? (
                      <div className="framework-list">
                        <strong>Recommendations</strong>
                        {check.recommendations.map((recommendation) => (
                          <p key={recommendation}>{recommendation}</p>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </Panel>
          </>
        ) : (
          <EmptyState
            title="No compliance report yet"
            body="Run the checker to see framework gaps, recommendations, and modeled penalty risk."
            className="compact-empty-state"
          />
        )}
      </div>
    </div>
  )
}

interface DataViewProps {
  agentStatus: AgentStatus[]
  agentHistory: AgentRun[]
  agentsRunning: boolean
  onDownload: (path: string, filename: string, auth?: boolean) => void
  onRefreshStatus: () => void
  onForceRefresh: () => void
}

export function DataView({
  agentStatus,
  agentHistory,
  agentsRunning,
  onDownload,
  onRefreshStatus,
  onForceRefresh,
}: DataViewProps) {
  const downloadCards = [
    ['/api/exports/scenarios.xlsx', 'scenarios.xlsx', 'Scenarios (Excel)', true],
    ['/api/exports/scenarios.json', 'scenarios.json', 'Scenarios (JSON)', true],
    ['/api/exports/emission-factors.xlsx', 'emission-factors.xlsx', 'Emission Factors (Excel)', false],
    ['/api/exports/emission-factors.json', 'emission-factors.json', 'Emission Factors (JSON)', false],
    ['/api/exports/agent-runs.xlsx', 'agent-runs.xlsx', 'Agent Runs (Excel)', true],
  ] as const

  return (
    <div className="workspace-grid">
      <div className="download-grid">
        {downloadCards.map(([path, filename, label, auth]) => (
          <button key={filename} className="download-card" onClick={() => onDownload(path, filename, auth)} type="button">
            <span className="eyebrow">Export</span>
            <strong>{label}</strong>
            <p>{filename}</p>
          </button>
        ))}
      </div>

      <div className="analysis-grid">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Agent status</span>
              <h3>TinyFish factor refresh</h3>
            </div>
            <div className="hero-actions">
              <Button tone="soft" onClick={onRefreshStatus}>
                Refresh
              </Button>
              <Button tone="primary" busy={agentsRunning} onClick={onForceRefresh}>
                Force re-fetch
              </Button>
            </div>
          </div>
          {agentStatus.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Category</th>
                    <th>Last run</th>
                    <th>Status</th>
                    <th>Cache</th>
                  </tr>
                </thead>
                <tbody>
                  {agentStatus.map((agent) => (
                    <tr key={agent.name}>
                      <td>{agent.name}</td>
                      <td>{agent.category}</td>
                      <td>{formatDateTime(agent.last_run ?? null)}</td>
                      <td>{agent.last_status ?? 'pending'}</td>
                      <td>{agent.cache_valid ? 'Valid' : 'Stale'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="subtle-copy">No agent data loaded yet.</p>
          )}
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Run history</span>
              <h3>Latest agent activity</h3>
            </div>
          </div>
          {agentHistory.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Run ID</th>
                    <th>Steps</th>
                    <th>Fetched</th>
                  </tr>
                </thead>
                <tbody>
                  {agentHistory.map((run) => (
                    <tr key={run.id}>
                      <td>{run.agent_name}</td>
                      <td>{run.status}</td>
                      <td>{run.run_id ? run.run_id.slice(0, 12) : '—'}</td>
                      <td>{run.num_steps ?? '—'}</td>
                      <td>{formatDateTime(run.fetched_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="subtle-copy">No run history loaded yet.</p>
          )}
        </Panel>
      </div>
    </div>
  )
}
