import { startTransition, useCallback, useEffect, useState } from 'react'
import { DashboardView } from './components/dashboard'
import { ToastViewport, Button } from './components/primitives'
import {
  AuthView,
  ChatView,
  ComplianceView,
  DataView,
  FinancialView,
  OffsetsView,
  ScenariosView,
} from './components/views'
import './App.css'
import { api } from './lib/api'
import {
  NAV_ITEMS,
  createDefaultComplianceInput,
  createDefaultFinancialCalc,
  createDefaultOffsetPurchase,
  createDefaultScenarioDraft,
} from './lib/constants'
import {
  applyExtractedData,
  buildScenarioPayload,
  financialPresetFromScenario,
} from './lib/format'
import type {
  AgentRun,
  AgentStatus,
  AuthMode,
  ChatMessage,
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
  ScenarioDraft,
  TabId,
  Toast,
  UserOut,
} from './types'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard')
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [currentUser, setCurrentUser] = useState<UserOut | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('cc_token'))
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    () => localStorage.getItem('cc_selected_scenario_id'),
  )
  const [scenarioDraft, setScenarioDraft] = useState<ScenarioDraft>(createDefaultScenarioDraft)
  const [editingScenario, setEditingScenario] = useState<Scenario | null>(null)
  const [scenarioLoading, setScenarioLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<ReductionSuggestion[]>([])
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatContext, setChatContext] = useState<Record<string, unknown>>({})
  const [sessionId] = useState(() => `session-${Math.random().toString(36).slice(2, 9)}`)
  const [financialCalc, setFinancialCalc] = useState(createDefaultFinancialCalc)
  const [financialResult, setFinancialResult] = useState<FinancialResult | null>(null)
  const [financialLoading, setFinancialLoading] = useState(false)
  const [offsetProjects, setOffsetProjects] = useState<Record<string, OffsetProject>>({})
  const [offsetRegistries, setOffsetRegistries] = useState<Record<string, OffsetRegistry>>({})
  const [offsetMarket, setOffsetMarket] = useState<OffsetMarket | null>(null)
  const [offsetPurchases, setOffsetPurchases] = useState<OffsetPurchase[]>([])
  const [offsetPortfolio, setOffsetPortfolio] = useState<OffsetPortfolioSummary | null>(null)
  const [offsetRecommendations, setOffsetRecommendations] = useState<OffsetRecommendation[]>([])
  const [offsetDraft, setOffsetDraft] = useState(createDefaultOffsetPurchase)
  const [offsetLoading, setOffsetLoading] = useState(false)
  const [complianceInput, setComplianceInput] = useState(createDefaultComplianceInput)
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null)
  const [complianceLoading, setComplianceLoading] = useState(false)
  const [agentStatus, setAgentStatus] = useState<AgentStatus[]>([])
  const [agentHistory, setAgentHistory] = useState<AgentRun[]>([])
  const [agentsRunning, setAgentsRunning] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const selectedScenario = scenarios.find((scenario) => scenario.scenario_id === selectedScenarioId) ?? scenarios[0] ?? null
  const currentNav = NAV_ITEMS.find((item) => item.id === activeTab) ?? NAV_ITEMS[0]

  const pushToast = useCallback((
    message: string,
    tone: Toast['tone'] = 'success',
  ) => {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setToasts((current) => [...current, { id, message, tone }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 3200)
  }, [])

  const clearSession = () => {
    setToken(null)
    setCurrentUser(null)
    setScenarios([])
    setSelectedScenarioId(null)
    setSuggestions([])
    setFinancialResult(null)
    setOffsetPurchases([])
    setOffsetPortfolio(null)
    setOffsetRecommendations([])
    setComplianceReport(null)
    localStorage.removeItem('cc_token')
    localStorage.removeItem('cc_selected_scenario_id')
  }

  useEffect(() => {
    if (!token) return
    localStorage.setItem('cc_token', token)
  }, [pushToast, token])

  useEffect(() => {
    if (selectedScenario?.scenario_id) {
      localStorage.setItem('cc_selected_scenario_id', selectedScenario.scenario_id)
      return
    }
    localStorage.removeItem('cc_selected_scenario_id')
  }, [selectedScenario?.scenario_id])

  useEffect(() => {
    if (!scenarios.length) {
      setSelectedScenarioId(null)
      return
    }
    if (!selectedScenarioId || !scenarios.some((scenario) => scenario.scenario_id === selectedScenarioId)) {
      setSelectedScenarioId(scenarios[0].scenario_id)
    }
  }, [scenarios, selectedScenarioId])

  useEffect(() => {
    if (!selectedScenario) return
    const preset = financialPresetFromScenario(selectedScenario)
    setFinancialCalc((current) => ({
      ...current,
      baseline: preset.baseline ?? current.baseline,
      energy_kwh: preset.energy_kwh ?? current.energy_kwh,
      meal_switches: preset.meal_switches ?? current.meal_switches,
      linked_scenario_id: preset.linked_scenario_id ?? current.linked_scenario_id,
      linked_scenario_name: preset.linked_scenario_name ?? current.linked_scenario_name,
    }))
    setComplianceInput((current) => ({
      ...current,
      total_tco2e: selectedScenario.emissions.total_tco2e,
      attendees: selectedScenario.attendees,
      event_days: selectedScenario.event_days,
    }))
  }, [selectedScenario])

  useEffect(() => {
    if (!token) return
    let active = true

    ;(async () => {
      try {
        const [user, loadedScenarios] = await Promise.all([
          api.me(token),
          api.listScenarios(token),
        ])
        if (!active) return
        startTransition(() => {
          setCurrentUser(user)
          setScenarios(loadedScenarios)
        })
      } catch (error) {
        if (!active) return
        clearSession()
        pushToast(error instanceof Error ? error.message : 'Session expired', 'warning')
      }
    })()

    return () => {
      active = false
    }
  }, [pushToast, token])

  const loadOffsetWorkspace = useCallback(async () => {
    if (!token) return
    try {
      const [projects, registries, market, purchases, portfolio] = await Promise.all([
        api.listOffsetProjects(),
        api.listOffsetRegistries(),
        api.getOffsetMarket(),
        api.listOffsetPurchases(token),
        api.getOffsetPortfolio(token, selectedScenario?.scenario_id ?? null),
      ])
      setOffsetProjects(projects)
      setOffsetRegistries(registries)
      setOffsetMarket(market)
      setOffsetPurchases(purchases)
      setOffsetPortfolio(portfolio)
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Failed to load offsets', 'warning')
    }
  }, [pushToast, selectedScenario?.scenario_id, token])

  const loadAgentPanels = useCallback(async () => {
    if (!token) return
    try {
      const [status, history] = await Promise.all([
        api.getAgentStatus(token),
        api.getAgentHistory(token),
      ])
      setAgentStatus(status)
      setAgentHistory(history)
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Failed to load agent data', 'warning')
    }
  }, [pushToast, token])

  useEffect(() => {
    if (!token) return
    if (activeTab === 'offsets') {
      void loadOffsetWorkspace()
    }
    if (activeTab === 'data') {
      void loadAgentPanels()
    }
  }, [activeTab, loadAgentPanels, loadOffsetWorkspace, token, selectedScenario?.scenario_id])

  async function handleAuthSubmit() {
    setAuthLoading(true)
    setAuthError('')
    try {
      const payload =
        authMode === 'login'
          ? await api.login(authEmail, authPassword)
          : await api.register(authEmail, authPassword)
      setToken(payload.access_token)
      setCurrentUser(payload.user)
      setAuthEmail('')
      setAuthPassword('')
      pushToast(authMode === 'login' ? 'Signed in successfully' : 'Account created', 'success')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication failed'
      setAuthError(message)
    } finally {
      setAuthLoading(false)
    }
  }

  function handleOpenTab(tab: TabId) {
    startTransition(() => setActiveTab(tab))
  }

  function handleLogout() {
    clearSession()
    pushToast('Signed out', 'neutral')
  }

  async function handleScenarioSubmit() {
    if (!token) return
    setScenarioLoading(true)
    try {
      const payload = buildScenarioPayload(scenarioDraft, scenarios.length)
      const nextScenario = editingScenario
        ? await api.updateScenario(editingScenario.scenario_id, payload, token)
        : await api.createScenario(payload, token)

      setScenarios((current) => {
        const next = editingScenario
          ? current.map((scenario) =>
              scenario.scenario_id === editingScenario.scenario_id ? nextScenario : scenario,
            )
          : [nextScenario, ...current]
        return next
      })
      setEditingScenario(null)
      setScenarioDraft(createDefaultScenarioDraft())
      setSelectedScenarioId(nextScenario.scenario_id)
      pushToast(
        `${editingScenario ? 'Updated' : 'Created'} ${nextScenario.name} · ${nextScenario.emissions.total_tco2e.toFixed(2)} tCO2e`,
      )
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Scenario calculation failed', 'danger')
    } finally {
      setScenarioLoading(false)
    }
  }

  function handleEditScenario(scenario: Scenario) {
    const payload = scenario.input_payload
    setEditingScenario(scenario)
    setScenarioDraft({
      name: scenario.name,
      event_type: scenario.event_type,
      attendees: scenario.attendees,
      event_days: scenario.event_days,
      location: payload?.location ?? scenario.location,
      venue_grid: payload?.venue_energy?.grid_region ?? 'singapore',
      catering_type: payload?.catering?.catering_type ?? 'mixed_buffet',
      include_alcohol: payload?.catering?.include_alcohol ?? false,
      accommodation_type: payload?.accommodation?.accommodation_type ?? 'standard_hotel',
      renewable_pct: payload?.venue_energy?.renewable_pct ?? 0,
      travel_segments: payload?.travel_segments ?? [],
      stage_m2: payload?.equipment?.stage_m2 ?? 0,
      lighting_days: payload?.equipment?.lighting_days ?? 0,
      sound_system_days: payload?.equipment?.sound_system_days ?? 0,
      led_screen_m2: payload?.equipment?.led_screen_m2 ?? 0,
      generator_hours: payload?.equipment?.generator_hours ?? 0,
      tshirts: payload?.swag?.tshirts ?? 0,
      tshirt_type: payload?.swag?.tshirt_type ?? 'cotton',
      tote_bags: payload?.swag?.tote_bags ?? 0,
      lanyards: payload?.swag?.lanyards ?? 0,
      badges: payload?.swag?.badges ?? 0,
    })
    handleOpenTab('scenarios')
  }

  function handleCancelEdit() {
    setEditingScenario(null)
    setScenarioDraft(createDefaultScenarioDraft())
  }

  async function handleCloneScenario(scenario: Scenario) {
    if (!token) return
    const nextName = window.prompt('Name for cloned scenario', `Copy of ${scenario.name}`)
    if (!nextName) return
    try {
      const cloned = await api.cloneScenario(scenario.scenario_id, nextName, token)
      setScenarios((current) => [cloned, ...current])
      setSelectedScenarioId(cloned.scenario_id)
      pushToast(`Cloned ${nextName}`, 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Clone failed', 'danger')
    }
  }

  async function handleDeleteScenario(id: string) {
    if (!token) return
    if (!window.confirm('Delete this scenario?')) return
    try {
      await api.deleteScenario(id, token)
      setScenarios((current) => current.filter((scenario) => scenario.scenario_id !== id))
      setSuggestions([])
      pushToast('Scenario deleted', 'neutral')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Delete failed', 'danger')
    }
  }

  async function handleExportScenario(scenario: Scenario) {
    if (!token) return
    try {
      const payload = await api.exportScenario(scenario.scenario_id, token)
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `cutcarbon_${scenario.scenario_id}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      pushToast('Scenario report exported', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Export failed', 'danger')
    }
  }

  async function handleLoadSuggestions(scenario: Scenario) {
    if (!token) return
    try {
      const loaded = await api.getScenarioSuggestions(scenario.scenario_id, token)
      setSuggestions(loaded)
      setSelectedScenarioId(scenario.scenario_id)
      pushToast('Reduction suggestions loaded', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Suggestions failed', 'danger')
    }
  }

  async function handleSendChat(messageOverride?: string) {
    if (!token) return
    const content = (messageOverride ?? chatInput).trim()
    if (!content) return
    const nextMessage: ChatMessage = { role: 'user', content }
    const nextMessages = [...chatMessages, nextMessage]
    setChatMessages(nextMessages)
    if (!messageOverride) {
      setChatInput('')
    } else {
      setChatInput('')
    }
    setChatLoading(true)
    try {
      const response = await api.sendChat(
        nextMessages,
        { ...chatContext, session_id: sessionId },
        token,
        selectedScenario?.scenario_id,
      )
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.reply,
        extracted_data: response.extracted_data ?? undefined,
      }
      setChatMessages((current) => [...current, assistantMessage])
      setChatContext((current) => ({
        ...current,
        event_name: response.extracted_data?.event_name ?? current.event_name,
        attendees: response.extracted_data?.attendees ?? current.attendees,
        location: response.extracted_data?.location ?? current.location,
      }))
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Chat failed', 'danger')
    } finally {
      setChatLoading(false)
    }
  }

  function handleApplyExtracted(data: Record<string, unknown>) {
    setScenarioDraft((current) => applyExtractedData(current, data))
    handleOpenTab('scenarios')
    pushToast('Extracted data applied to scenario builder', 'success')
  }

  async function handleCalculateSavings() {
    if (!token) return
    setFinancialLoading(true)
    try {
      const reduced = financialCalc.baseline * (1 - financialCalc.reduction_pct / 100)
      const result = await api.calculateSavings(
        {
          scenario_id: financialCalc.linked_scenario_id,
          baseline_tco2e: financialCalc.baseline,
          reduced_tco2e: reduced,
          region: financialCalc.region,
          energy_kwh_saved: financialCalc.energy_kwh,
          meal_switches: financialCalc.meal_switches,
          attendees: complianceInput.attendees,
          actions_taken: financialCalc.actions,
        },
        token,
      )
      setFinancialResult(result)
      pushToast(`Modeled ${result.co2e_reduction_pct.toFixed(1)}% reduction`, 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Savings calculation failed', 'danger')
    } finally {
      setFinancialLoading(false)
    }
  }

  async function handleCreateOffset() {
    if (!token) return
    setOffsetLoading(true)
    try {
      await api.createOffsetPurchase(
        {
          scenario_id: selectedScenario?.scenario_id ?? null,
          ...offsetDraft,
        },
        token,
      )
      setOffsetDraft(createDefaultOffsetPurchase())
      await loadOffsetWorkspace()
      pushToast('Offset purchase recorded', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Offset purchase failed', 'danger')
    } finally {
      setOffsetLoading(false)
    }
  }

  async function handleRetireOffset(id: number) {
    if (!token) return
    try {
      await api.retireOffset(id, token)
      await loadOffsetWorkspace()
      pushToast('Credit retired', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Retirement failed', 'danger')
    }
  }

  async function handleCancelOffset(id: number) {
    if (!token) return
    if (!window.confirm('Cancel this offset purchase?')) return
    try {
      await api.cancelOffset(id, token)
      await loadOffsetWorkspace()
      pushToast('Purchase cancelled', 'neutral')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Cancellation failed', 'danger')
    }
  }

  async function handleLoadOffsetRecommendations() {
    if (!token || !selectedScenario) return
    try {
      const recommendations = await api.getOffsetRecommendations(selectedScenario.scenario_id, token)
      setOffsetRecommendations(recommendations)
      pushToast('Offset recommendations generated', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Recommendation load failed', 'danger')
    }
  }

  async function handleCheckCompliance() {
    setComplianceLoading(true)
    try {
      const params = new URLSearchParams({
        total_tco2e: String(complianceInput.total_tco2e),
        has_scope3: String(complianceInput.has_scope3),
        has_ghg_report: String(complianceInput.has_ghg_report),
        region: complianceInput.region,
        event_days: String(complianceInput.event_days),
        attendees: String(complianceInput.attendees),
      })
      const report = await api.checkCompliance(params)
      setComplianceReport(report)
      pushToast(`Compliance score ${report.overall_score_pct.toFixed(0)}%`, 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Compliance check failed', 'danger')
    } finally {
      setComplianceLoading(false)
    }
  }

  async function handleDownload(path: string, filename: string, auth = false) {
    try {
      await api.download(path, filename, auth ? token : null)
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Download failed', 'danger')
    }
  }

  async function handleRefreshAgents() {
    if (!token) return
    setAgentsRunning(true)
    try {
      try {
        await api.runAgentsSync(token)
      } catch {
        pushToast('Factor refresh agent unavailable, recalculating with current factors.', 'warning')
      }
      const recalc = await api.recalculateScenarios(token)
      setScenarios(recalc.scenarios)
      pushToast(
        `${recalc.updated_count} scenario${recalc.updated_count === 1 ? '' : 's'} recalculated`,
        recalc.failed_count ? 'warning' : 'success',
      )
      await loadAgentPanels()
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Refresh failed', 'danger')
    } finally {
      setAgentsRunning(false)
    }
  }

  async function handleForceRefreshAgents() {
    if (!token) return
    setAgentsRunning(true)
    try {
      await api.runAgentsForce(token)
      await loadAgentPanels()
      pushToast('Force refresh dispatched', 'success')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Force refresh failed', 'danger')
    } finally {
      setAgentsRunning(false)
    }
  }

  let workspace = null

  switch (activeTab) {
    case 'dashboard':
      workspace = (
        <DashboardView
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          suggestions={suggestions}
          financialCalc={financialCalc}
          financialResult={financialResult}
          complianceReport={complianceReport}
          onSelectScenario={(scenario) => setSelectedScenarioId(scenario.scenario_id)}
          onOpenTab={handleOpenTab}
          onLoadSuggestions={handleLoadSuggestions}
        />
      )
      break
    case 'chat':
      workspace = (
        <ChatView
          messages={chatMessages}
          chatInput={chatInput}
          chatLoading={chatLoading}
          selectedScenario={selectedScenario}
          onChatInputChange={setChatInput}
          onSend={() => void handleSendChat()}
          onApplyExtracted={handleApplyExtracted}
          onUseSuggestion={(prompt) => {
            void handleSendChat(prompt)
          }}
        />
      )
      break
    case 'scenarios':
      workspace = (
        <ScenariosView
          draft={scenarioDraft}
          setDraft={setScenarioDraft}
          scenarioLoading={scenarioLoading}
          editingScenario={editingScenario}
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          suggestions={suggestions}
          onSubmit={handleScenarioSubmit}
          onCancelEdit={handleCancelEdit}
          onEdit={handleEditScenario}
          onClone={handleCloneScenario}
          onDelete={handleDeleteScenario}
          onExport={handleExportScenario}
          onSelectScenario={(scenario) => setSelectedScenarioId(scenario.scenario_id)}
          onLoadSuggestions={handleLoadSuggestions}
        />
      )
      break
    case 'financial':
      workspace = (
        <FinancialView
          calc={financialCalc}
          setCalc={setFinancialCalc}
          result={financialResult}
          loading={financialLoading}
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          onCalculate={handleCalculateSavings}
        />
      )
      break
    case 'offsets':
      workspace = (
        <OffsetsView
          selectedScenario={selectedScenario}
          projects={offsetProjects}
          registries={offsetRegistries}
          market={offsetMarket}
          purchases={offsetPurchases}
          portfolio={offsetPortfolio}
          recommendations={offsetRecommendations}
          draft={offsetDraft}
          setDraft={setOffsetDraft}
          loading={offsetLoading}
          onCreate={handleCreateOffset}
          onRetire={handleRetireOffset}
          onCancel={handleCancelOffset}
          onLoadRecommendations={handleLoadOffsetRecommendations}
        />
      )
      break
    case 'compliance':
      workspace = (
        <ComplianceView
          input={complianceInput}
          setInput={setComplianceInput}
          report={complianceReport}
          loading={complianceLoading}
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          onCheck={handleCheckCompliance}
        />
      )
      break
    case 'data':
      workspace = (
        <DataView
          agentStatus={agentStatus}
          agentHistory={agentHistory}
          agentsRunning={agentsRunning}
          onDownload={handleDownload}
          onRefreshStatus={loadAgentPanels}
          onForceRefresh={handleForceRefreshAgents}
        />
      )
      break
  }

  if (!currentUser || !token) {
    return (
      <>
        <AuthView
          mode={authMode}
          email={authEmail}
          password={authPassword}
          error={authError}
          busy={authLoading}
          onModeChange={setAuthMode}
          onEmailChange={setAuthEmail}
          onPasswordChange={setAuthPassword}
          onSubmit={handleAuthSubmit}
        />
        <ToastViewport toasts={toasts} />
      </>
    )
  }

  return (
    <>
      <div className="app-shell">
        <aside className="workspace-rail">
          <div className="rail-brand">
            <img className="app-logo" src="/favicon.svg" alt="CutCarbon logo" />
            <div>
              <strong>CutCarbon</strong>
            </div>
          </div>
          <nav className="rail-nav">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                className={item.id === activeTab ? 'rail-link is-active' : 'rail-link'}
                onClick={() => handleOpenTab(item.id)}
                type="button"
              >
                <span className="rail-link-mark" style={{ background: item.accent }} />
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          <div className="rail-foot">
            <span>{currentUser.email}</span>
            <Button tone="ghost" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </aside>

        <main className="workspace-main">
          <header className="workspace-header">
            <div>
              <h2>{currentNav.label}</h2>
              <p>{currentNav.description}</p>
            </div>
            <div className="workspace-header-actions">
              <Button tone="soft" busy={agentsRunning} onClick={handleRefreshAgents}>
                Refresh factors
              </Button>
              <Button tone="primary" onClick={() => handleOpenTab('chat')}>
                Ask co-pilot
              </Button>
            </div>
          </header>

          {workspace}
        </main>
      </div>
      <ToastViewport toasts={toasts} />
    </>
  )
}

export default App
