import type { ChartConfiguration } from 'chart.js'
import {
  EMISSION_CATEGORIES,
  QUICK_ACTIONS,
} from '../lib/constants'
import {
  bestScenario,
  buildFlowDiagram,
  estimatedReductionOpportunity,
  formatCurrency,
  formatKgPerAttendee,
  formatNumber,
  formatTons,
  intensityBand,
  scenarioGapToBest,
  scenarioRank,
  selectedScenarioCategoryRows,
  selectedScenarioFactorRows,
  selectedScenarioOpportunityRows,
  selectedScenarioScopeRows,
  shortScenarioName,
  sortScenariosByTotal,
  topEmissionSource,
} from '../lib/format'
import type {
  ComplianceReport,
  FinancialCalcState,
  FinancialResult,
  ReductionSuggestion,
  Scenario,
  TabId,
} from '../types'
import { Badge, Button, ChartSurface, EmptyState, MermaidSurface, MetricCard, Panel } from './primitives'

interface DashboardViewProps {
  scenarios: Scenario[]
  selectedScenario: Scenario | null
  suggestions: ReductionSuggestion[]
  financialCalc: FinancialCalcState
  financialResult: FinancialResult | null
  complianceReport: ComplianceReport | null
  onSelectScenario: (scenario: Scenario) => void
  onOpenTab: (tab: TabId) => void
  onLoadSuggestions: (scenario: Scenario) => void
}

export function DashboardView({
  scenarios,
  selectedScenario,
  suggestions,
  financialCalc,
  financialResult,
  complianceReport,
  onSelectScenario,
  onOpenTab,
  onLoadSuggestions,
}: DashboardViewProps) {
  if (!scenarios.length || !selectedScenario) {
    return (
      <div className="workspace-grid">
        <Panel className="hero-shell hero-shell-empty">
          <div className="hero-copy">
            <span className="eyebrow">Carbon Intelligence Workspace</span>
            <h2>Create your first scenario to activate portfolio analytics.</h2>
            <p>
              Once a baseline event is created, this dashboard will compare portfolio totals,
              map scope composition, and prioritize reduction actions.
            </p>
            <div className="hero-actions hero-actions-row">
              <Button tone="primary" onClick={() => onOpenTab('scenarios')}>
                Create scenario
              </Button>
              <Button tone="soft" onClick={() => onOpenTab('chat')}>
                Open AI assistant
              </Button>
            </div>
          </div>
          <div className="quick-actions">
            {QUICK_ACTIONS.map((action) => (
              <article key={action.title} className="quick-action-card">
                <span className="quick-action-title">{action.title}</span>
                <p>{action.body}</p>
              </article>
            ))}
          </div>
        </Panel>
        <EmptyState
          title="No scenario data available"
          body="Create a baseline event or use the AI assistant to draft one from natural language."
        />
      </div>
    )
  }

  const sortedScenarios = sortScenariosByTotal(scenarios)
  const selectedCategories = selectedScenarioCategoryRows(selectedScenario)
  const selectedScopes = selectedScenarioScopeRows(selectedScenario)
  const selectedOpportunities = selectedScenarioOpportunityRows(selectedScenario)
  const factorRows = selectedScenarioFactorRows(selectedScenario.factors_snapshot)
  const hotspot = topEmissionSource(selectedScenario)
  const best = bestScenario(scenarios)
  const complianceScore = complianceReport?.overall_score_pct ?? null

  const portfolioConfig: ChartConfiguration<'bar' | 'line'> | null = sortedScenarios.length
    ? {
        type: 'bar',
        data: {
          labels: sortedScenarios.map((scenario) => shortScenarioName(scenario.name)),
          datasets: [
            {
              type: 'bar',
              label: 'Total tCO2e',
              data: sortedScenarios.map((scenario) => Number(scenario.emissions.total_tco2e.toFixed(3))),
              backgroundColor: sortedScenarios.map((scenario) =>
                scenario.scenario_id === selectedScenario.scenario_id ? '#1f6f6d' : 'rgba(31,111,109,0.16)',
              ),
              borderColor: '#1f6f6d',
              borderRadius: 8,
              borderWidth: 0,
              yAxisID: 'y',
            },
            {
              type: 'line',
              label: 'kg / attendee',
              data: sortedScenarios.map((scenario) =>
                Number((scenario.emissions.per_attendee_tco2e * 1000).toFixed(1)),
              ),
              borderColor: '#3b6e8f',
              tension: 0.4,
              borderDash: [5, 4],
              pointRadius: 3,
              pointBackgroundColor: '#3b6e8f',
              yAxisID: 'y1',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              labels: { color: '#64748b', boxWidth: 10, padding: 16 },
            },
          },
          scales: {
            x: {
              ticks: { color: '#94a3b8', font: { size: 11 } },
              grid: { display: false },
              border: { display: false },
            },
            y: {
              ticks: {
                color: '#1f6f6d',
                font: { size: 11 },
                callback: (value) => `${value} t`,
              },
              grid: { color: 'rgba(15,23,42,0.05)' },
              border: { display: false },
            },
            y1: {
              position: 'right',
              ticks: {
                color: '#3b6e8f',
                font: { size: 11 },
                callback: (value) => `${value} kg`,
              },
              grid: { drawOnChartArea: false },
              border: { display: false },
            },
          },
        },
      }
    : null

  const stackConfig: ChartConfiguration<'bar'> | null = sortedScenarios.length
    ? {
        type: 'bar',
        data: {
          labels: sortedScenarios.map((scenario) => shortScenarioName(scenario.name)),
          datasets: EMISSION_CATEGORIES.map((category) => ({
            label: category.label,
            data: sortedScenarios.map((scenario) =>
              Number((scenario.emissions[category.key as keyof typeof scenario.emissions] as number).toFixed(3)),
            ),
            backgroundColor: category.color,
            borderRadius: 4,
            borderSkipped: false,
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: {
            legend: {
              labels: { color: '#64748b', boxWidth: 10, padding: 16 },
            },
          },
          scales: {
            x: {
              stacked: true,
              ticks: { color: '#94a3b8', font: { size: 11 }, callback: (value) => `${value} t` },
              grid: { color: 'rgba(15,23,42,0.05)' },
              border: { display: false },
            },
            y: {
              stacked: true,
              ticks: { color: '#64748b', font: { size: 11 } },
              grid: { display: false },
              border: { display: false },
            },
          },
        },
      }
    : null

  const mixConfig: ChartConfiguration<'doughnut'> | null = selectedCategories.length
    ? {
        type: 'doughnut',
        data: {
          labels: selectedCategories.map((row) => row.label),
          datasets: [
            {
              data: selectedCategories.map((row) => row.value),
              backgroundColor: selectedCategories.map((row) => row.color),
              borderWidth: 0,
              hoverOffset: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#64748b', boxWidth: 10, padding: 14 },
            },
          },
        },
      }
    : null

  const scopeConfig: ChartConfiguration<'bar'> | null = selectedScopes.length
    ? {
        type: 'bar',
        data: {
          labels: selectedScopes.map((row) => row.label),
          datasets: [
            {
              data: selectedScopes.map((row) => row.value),
              backgroundColor: selectedScopes.map((row) => row.color),
              borderRadius: 8,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: {
              ticks: { color: '#94a3b8', font: { size: 11 }, callback: (value) => `${value} t` },
              grid: { color: 'rgba(15,23,42,0.05)' },
              border: { display: false },
            },
            y: {
              ticks: { color: '#64748b', font: { size: 11 } },
              grid: { display: false },
              border: { display: false },
            },
          },
        },
      }
    : null

  const opportunityConfig: ChartConfiguration<'bar'> | null = selectedOpportunities.length
    ? {
        type: 'bar',
        data: {
          labels: selectedOpportunities.map((row) => row.label),
          datasets: [
            {
              label: 'Potential tCO2e reduction',
              data: selectedOpportunities.map((row) => row.value),
              backgroundColor: selectedOpportunities.map((row) => row.color),
              borderRadius: 8,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#94a3b8', font: { size: 11 }, callback: (value) => `${value} t` }, grid: { color: 'rgba(15,23,42,0.05)' }, border: { display: false } },
            y: { ticks: { color: '#64748b', font: { size: 11 } }, grid: { display: false }, border: { display: false } },
          },
        },
      }
    : null

  const factorConfig: ChartConfiguration<'bar'> | null = factorRows.length
    ? {
        type: 'bar',
        data: {
          labels: factorRows.map((row) => row.label),
          datasets: [
            {
              label: 'Applied factor',
              data: factorRows.map((row) => row.value),
              backgroundColor: factorRows.map((row) => row.color),
              borderRadius: 6,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => {
                  const row = factorRows[context.dataIndex]
                  return ` ${context.raw} ${row?.unit ?? ''}`
                },
              },
            },
          },
          scales: {
            x: {
              ticks: { color: '#94a3b8', font: { size: 11 }, maxRotation: 0, autoSkip: false },
              grid: { display: false },
              border: { display: false },
            },
            y: { ticks: { color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(15,23,42,0.05)' }, border: { display: false } },
          },
        },
      }
    : null

  const pathwayConfig: ChartConfiguration<'line'> = {
    type: 'line',
    data: {
      labels: ['Current', 'Operational cuts', 'Residual', 'Offset-ready'],
      datasets: [
        {
          label: 'tCO2e',
          data: [
            selectedScenario.emissions.total_tco2e,
            selectedScenario.emissions.total_tco2e - estimatedReductionOpportunity(selectedScenario),
            Math.max(selectedScenario.emissions.total_tco2e - estimatedReductionOpportunity(selectedScenario), 0),
            0,
          ],
          borderColor: '#1f6f6d',
          backgroundColor: 'rgba(31,111,109,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: '#1f6f6d',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { display: false }, border: { display: false } },
        y: { ticks: { color: '#64748b', font: { size: 11 }, callback: (value) => `${value} t` }, grid: { color: 'rgba(15,23,42,0.05)' }, border: { display: false } },
      },
    },
  }

  return (
    <div className="workspace-grid">
      <Panel className="hero-shell hero-shell-compact">
        <div className="hero-copy">
          <span className="eyebrow">Executive brief</span>
          <p className="hero-compact-copy">Portfolio at a glance. Focus area: {hotspot.label} emissions.</p>
          <div className="hero-signal-row">
            <Badge tone="fresh">{scenarios.length} scenario{scenarios.length === 1 ? '' : 's'}</Badge>
            <Badge tone="cyan">{intensityBand(selectedScenario)}</Badge>
          </div>
        </div>
        <div className="hero-summary">
          <span className="eyebrow">Active scenario</span>
          <strong>{selectedScenario.name}</strong>
          <p>{formatTons(selectedScenario.emissions.total_tco2e, 3)}</p>
          <div className="hero-actions hero-actions-row">
            <Button tone="soft" onClick={() => onOpenTab('scenarios')}>
              Edit scenario
            </Button>
            <Button tone="primary" onClick={() => onOpenTab('financial')}>
              Price the plan
            </Button>
          </div>
        </div>
      </Panel>

      <Panel className="scenario-picker-panel">
        <div className="scenario-picker-head">
          <span className="eyebrow">Scenarios</span>
          <span className="eyebrow">{sortedScenarios.length} total</span>
        </div>
        <div className="scenario-chip-row" role="list" aria-label="Scenario list">
          {sortedScenarios.map((scenario) => (
            <button
              key={scenario.scenario_id}
              className={scenario.scenario_id === selectedScenario.scenario_id ? 'scenario-chip is-active' : 'scenario-chip'}
              onClick={() => onSelectScenario(scenario)}
              type="button"
            >
              <span>{scenario.name}</span>
              <small>{formatTons(scenario.emissions.total_tco2e)}</small>
            </button>
          ))}
        </div>
      </Panel>

      <div className="metric-grid">
        <MetricCard
          eyebrow="Current total"
          value={formatTons(selectedScenario.emissions.total_tco2e)}
          detail="Absolute event footprint"
        />
        <MetricCard
          eyebrow="Intensity / attendee"
          value={formatKgPerAttendee(selectedScenario.emissions.per_attendee_tco2e)}
          detail="Per attendee emissions efficiency"
          tone="cyan"
        />
        <MetricCard
          eyebrow="Gap to best"
          value={`${formatNumber(scenarioGapToBest(selectedScenario, scenarios), 1)}%`}
          detail={best ? `Best current plan: ${best.name}` : 'No portfolio baseline'}
          tone="amber"
        />
        <MetricCard
          eyebrow="Reduction opportunity"
          value={formatTons(estimatedReductionOpportunity(selectedScenario))}
          detail="Modeled top-category abatement"
          tone="rose"
        />
      </div>

      <div className="analysis-grid">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Portfolio comparison</span>
              <h3>Scenario scorecard</h3>
            </div>
            <p>Lowest total emissions rank first. The active scenario stays highlighted.</p>
          </div>
          <ChartSurface config={portfolioConfig} empty="Create at least one scenario to compare totals." />
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Category view</span>
              <h3>Category stack across all scenarios</h3>
            </div>
            <p>Travel, energy, catering, waste, and production compared side by side.</p>
          </div>
          <ChartSurface config={stackConfig} empty="Create at least one scenario to unlock comparison analytics." />
        </Panel>
      </div>

      <div className="analysis-grid analysis-grid-tight">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Selected mix</span>
              <h3>Category breakdown</h3>
            </div>
          </div>
          <ChartSurface config={mixConfig} empty="No category data for this scenario." height={260} />
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">GHG scopes</span>
              <h3>Scope distribution</h3>
            </div>
          </div>
          <ChartSurface config={scopeConfig} empty="Scope data not available yet." height={260} />
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Abatement model</span>
              <h3>Reduction opportunity</h3>
            </div>
          </div>
          <ChartSurface config={opportunityConfig} empty="No modeled reductions available yet." height={260} />
        </Panel>
      </div>

      <div className="analysis-grid">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Pathway</span>
              <h3>Operational path to net zero</h3>
            </div>
            <p>Shows how much of the current footprint could be cut before offsetting.</p>
          </div>
          <ChartSurface config={pathwayConfig} empty="Pathway data unavailable." />
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Decision signals</span>
              <h3>What matters most right now</h3>
            </div>
          </div>
          <div className="signal-grid">
            <article className="signal-card">
              <span className="eyebrow">Primary hotspot</span>
              <strong>{hotspot.label}</strong>
              <p>{formatTons(hotspot.value)}</p>
            </article>
            <article className="signal-card">
              <span className="eyebrow">Scenario rank</span>
              <strong>#{scenarioRank(selectedScenario, scenarios)} of {scenarios.length}</strong>
              <p>Ranked by lowest total emissions.</p>
            </article>
            <article className="signal-card">
              <span className="eyebrow">Savings signal</span>
              <strong>
                {financialResult && financialCalc.linked_scenario_id === selectedScenario.scenario_id
                  ? formatCurrency(financialResult.total_financial_savings_usd)
                  : formatCurrency(selectedScenario.emissions.total_tco2e * 0.3 * 25 * 0.74)}
              </strong>
              <p>
                {financialResult && financialCalc.linked_scenario_id === selectedScenario.scenario_id
                  ? 'From linked financial analysis.'
                  : 'Modeled at a 30% reduction.'}
              </p>
            </article>
            <article className="signal-card">
              <span className="eyebrow">Compliance pulse</span>
              <strong>{complianceScore ? `${formatNumber(complianceScore, 0)}%` : 'Run compliance check'}</strong>
              <p>Most recent compliance score in this workspace.</p>
            </article>
          </div>
        </Panel>
      </div>

      <div className="analysis-grid">
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Factor snapshot</span>
              <h3>Applied emission factors</h3>
            </div>
            <p>
              {selectedScenario.factors_snapshot?.ef_version
                ? `Emission factors v${String(selectedScenario.factors_snapshot.ef_version)}`
                : 'Latest factor snapshot when available.'}
            </p>
          </div>
          <ChartSurface
            config={factorConfig}
            empty="Factor snapshot unavailable. Run factor refresh to populate this view."
            height={260}
          />
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Flow</span>
              <h3>Emission flow diagram</h3>
            </div>
            <Button tone="soft" onClick={() => onLoadSuggestions(selectedScenario)}>
              Load reduction moves
            </Button>
          </div>
          <MermaidSurface
            diagram={buildFlowDiagram(selectedScenario)}
            empty="Select a scenario to generate its flow diagram."
          />
        </Panel>
      </div>

      {selectedScenario.benchmark ? (
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Benchmarking</span>
              <h3>Industry positioning</h3>
            </div>
            <p>Quick comparison against typical and best-practice event intensity.</p>
          </div>
          <div className="benchmark-grid">
            <article className="benchmark-card">
              <span className="eyebrow">Your footprint / attendee / day</span>
              <strong>{formatTons(selectedScenario.benchmark.your_per_attendee_day, 3)}</strong>
            </article>
            <article className="benchmark-card">
              <span className="eyebrow">Industry typical</span>
              <strong>{formatTons(selectedScenario.benchmark.industry_typical, 3)}</strong>
            </article>
            <article className="benchmark-card">
              <span className="eyebrow">Best practice</span>
              <strong>{formatTons(selectedScenario.benchmark.industry_best_practice, 3)}</strong>
            </article>
            <article className="benchmark-card">
              <span className="eyebrow">Position</span>
              <strong>{selectedScenario.benchmark.percentile_rank}</strong>
            </article>
          </div>
        </Panel>
      ) : null}

      {suggestions.length ? (
        <Panel>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Reduction moves</span>
              <h3>Top suggestions for the active scenario</h3>
            </div>
            <Badge tone="amber">Target: -30%</Badge>
          </div>
          <div className="suggestion-grid">
            {suggestions.map((suggestion) => (
              <article key={suggestion.action} className="suggestion-card">
                <div className="suggestion-meta">
                  <Badge
                    tone={
                      suggestion.difficulty === 'easy'
                        ? 'fresh'
                        : suggestion.difficulty === 'medium'
                          ? 'amber'
                          : 'rose'
                    }
                  >
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
  )
}
