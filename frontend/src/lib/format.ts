import { EMISSION_CATEGORIES } from './constants'
import type {
  FactorSnapshot,
  FinancialCalcState,
  Scenario,
  ScenarioDraft,
  ScenarioInputPayload,
  TravelSegment,
} from '../types'

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export function labelize(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(value)
}

export function formatCurrency(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '$0'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value)
}

export function formatTons(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0.00 tCO2e'
  return `${value.toFixed(digits)} tCO2e`
}

export function formatKgPerAttendee(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0 kg'
  return `${(value * 1000).toFixed(1)} kg`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function shortScenarioName(name: string, maxLength = 18): string {
  return name.length > maxLength ? `${name.slice(0, maxLength)}…` : name
}

function reductionFactorForCategory(key: string): number {
  return {
    travel_tco2e: 0.22,
    venue_energy_tco2e: 0.45,
    accommodation_tco2e: 0.18,
    catering_tco2e: 0.35,
    materials_waste_tco2e: 0.4,
    equipment_tco2e: 0.25,
    swag_tco2e: 0.5,
  }[key] ?? 0
}

export function estimatedReductionOpportunity(scenario: Scenario | null): number {
  if (!scenario) return 0
  return EMISSION_CATEGORIES.reduce((total, category) => {
    const amount = scenario.emissions[category.key as keyof typeof scenario.emissions]
    const value = typeof amount === 'number' ? amount : 0
    return total + value * reductionFactorForCategory(category.key)
  }, 0)
}

export function topEmissionSource(scenario: Scenario | null): { label: string; key: string; value: number } {
  if (!scenario) return { label: 'No hotspot', key: 'none', value: 0 }
  return EMISSION_CATEGORIES.map((category) => ({
    key: category.key,
    label: category.label,
    value: scenario.emissions[category.key as keyof typeof scenario.emissions] as number,
  })).sort((left, right) => right.value - left.value)[0] ?? { label: 'No hotspot', key: 'none', value: 0 }
}

export function intensityBand(scenario: Scenario | null): string {
  if (!scenario) return 'No scenario selected'
  const kgPerAttendee = (scenario.emissions.per_attendee_tco2e ?? 0) * 1000
  if (kgPerAttendee < 90) return 'Low-intensity profile'
  if (kgPerAttendee < 180) return 'Moderate-intensity profile'
  return 'High-intensity profile'
}

export function sortScenariosByTotal(scenarios: Scenario[]): Scenario[] {
  return [...scenarios].sort((left, right) => {
    const totalDiff = left.emissions.total_tco2e - right.emissions.total_tco2e
    if (totalDiff !== 0) return totalDiff
    return left.name.localeCompare(right.name)
  })
}

export function bestScenario(scenarios: Scenario[]): Scenario | null {
  return sortScenariosByTotal(scenarios)[0] ?? null
}

export function scenarioGapToBest(target: Scenario | null, scenarios: Scenario[]): number {
  if (!target) return 0
  const best = bestScenario(scenarios)
  if (!best || !target.emissions.total_tco2e) return 0
  return ((target.emissions.total_tco2e - best.emissions.total_tco2e) / target.emissions.total_tco2e) * 100
}

export function scenarioRank(target: Scenario | null, scenarios: Scenario[]): number {
  if (!target) return 0
  return sortScenariosByTotal(scenarios).findIndex((scenario) => scenario.scenario_id === target.scenario_id) + 1
}

export function selectedScenarioCategoryRows(scenario: Scenario | null) {
  if (!scenario) return []
  return EMISSION_CATEGORIES.map((category) => ({
    ...category,
    value: Number(scenario.emissions[category.key as keyof typeof scenario.emissions] ?? 0),
  }))
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value)
}

export function selectedScenarioScopeRows(scenario: Scenario | null) {
  if (!scenario?.emissions.scopes) return []
  return [
    { label: 'Scope 1', value: scenario.emissions.scopes.scope1_tco2e, color: '#f97316' },
    { label: 'Scope 2', value: scenario.emissions.scopes.scope2_tco2e, color: '#facc15' },
    { label: 'Scope 3', value: scenario.emissions.scopes.scope3_tco2e, color: '#14b8a6' },
  ]
}

export function selectedScenarioOpportunityRows(scenario: Scenario | null) {
  if (!scenario) return []
  return EMISSION_CATEGORIES.map((category) => {
    const value = Number(scenario.emissions[category.key as keyof typeof scenario.emissions] ?? 0)
    return {
      ...category,
      value: Number((value * reductionFactorForCategory(category.key)).toFixed(4)),
    }
  })
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value)
}

export function selectedScenarioFactorRows(snapshot?: FactorSnapshot) {
  if (!snapshot) return []
  const rows = [
    {
      label: 'Long-haul flight',
      unit: 'kg / pkm',
      value: Number(snapshot.travel_long_haul_economy_kg_per_pkm ?? 0),
      color: '#0891b2',
    },
    {
      label: 'Short-haul flight',
      unit: 'kg / pkm',
      value: Number(snapshot.travel_short_haul_economy_kg_per_pkm ?? 0),
      color: '#38bdf8',
    },
    {
      label: 'Petrol car',
      unit: 'kg / pkm',
      value: Number(snapshot.travel_car_petrol_kg_per_pkm ?? 0),
      color: '#f97316',
    },
    {
      label: `Grid ${labelize(String(snapshot.venue_grid_region ?? 'global'))}`,
      unit: 'kg / kWh',
      value: Number(snapshot.venue_grid_kg_per_kwh ?? 0),
      color: '#22c55e',
    },
    {
      label: `Catering ${labelize(String(snapshot.catering_type ?? 'mixed'))}`,
      unit: 'kg / meal',
      value: Number(snapshot.catering_kg_per_meal ?? 0),
      color: '#eab308',
    },
    {
      label: 'Accommodation',
      unit: 'kg / room-night',
      value: Number(snapshot.accommodation_kg_per_room_night ?? 0),
      color: '#8b5cf6',
    },
    {
      label: 'Waste landfill',
      unit: 'kg / kg',
      value: Number(snapshot.waste_landfill_kg_per_kg ?? 0),
      color: '#64748b',
    },
  ]
  return rows.filter((row) => row.value > 0)
}

export function buildScenarioPayload(draft: ScenarioDraft, scenarioCount: number): ScenarioInputPayload {
  const name = draft.name.trim() || `Scenario ${scenarioCount + 1}`
  const payload: ScenarioInputPayload = {
    name,
    event_name: `${draft.location} Event`,
    event_type: draft.event_type,
    location: draft.location,
    attendees: draft.attendees,
    event_days: draft.event_days,
    mode: 'basic',
    travel_segments: draft.travel_segments.map((segment: TravelSegment) => ({
      ...segment,
      label: segment.label || labelize(segment.mode),
    })),
    venue_energy: {
      grid_region: draft.venue_grid,
      renewable_pct: draft.renewable_pct,
    },
    catering: {
      catering_type: draft.catering_type,
      meals: draft.attendees * draft.event_days * 2,
      include_beverages: true,
      include_alcohol: draft.include_alcohol,
    },
    accommodation: {
      accommodation_type: draft.accommodation_type,
      room_nights: Math.ceil((draft.attendees * 0.8) / 1.5) * draft.event_days,
    },
  }

  if (
    draft.stage_m2 > 0 ||
    draft.lighting_days > 0 ||
    draft.sound_system_days > 0 ||
    draft.led_screen_m2 > 0 ||
    draft.generator_hours > 0
  ) {
    payload.equipment = {
      stage_m2: draft.stage_m2,
      lighting_days: draft.lighting_days,
      sound_system_days: draft.sound_system_days,
      led_screen_m2: draft.led_screen_m2,
      projectors: 0,
      generator_hours: draft.generator_hours,
      freight_tonne_km: 0,
    }
  }

  if (draft.tshirts > 0 || draft.tote_bags > 0 || draft.lanyards > 0 || draft.badges > 0) {
    payload.swag = {
      tshirts: draft.tshirts,
      tshirt_type: draft.tshirt_type,
      tote_bags: draft.tote_bags,
      lanyards: draft.lanyards,
      badges: draft.badges,
      badge_type: 'plastic',
      notebooks: 0,
      water_bottles: 0,
    }
  }

  return payload
}

export function applyExtractedData(
  draft: ScenarioDraft,
  extractedData: Record<string, unknown>,
): ScenarioDraft {
  const nextDraft = { ...draft }
  if (typeof extractedData.attendees === 'number') nextDraft.attendees = extractedData.attendees
  if (typeof extractedData.event_days === 'number') nextDraft.event_days = extractedData.event_days
  if (typeof extractedData.location === 'string') nextDraft.location = extractedData.location
  if (typeof extractedData.venue_grid_region === 'string') nextDraft.venue_grid = extractedData.venue_grid_region
  if (typeof extractedData.catering_type === 'string') nextDraft.catering_type = extractedData.catering_type
  if (typeof extractedData.accommodation_type === 'string') {
    nextDraft.accommodation_type = extractedData.accommodation_type
  }
  if (typeof extractedData.renewable_pct === 'number') nextDraft.renewable_pct = extractedData.renewable_pct
  if (Array.isArray(extractedData.travel_segments)) {
    const travelSegments: TravelSegment[] = []

    extractedData.travel_segments.forEach((item) => {
      if (!item || typeof item !== 'object') return
      const segment = item as Partial<TravelSegment>
      if (!segment.mode) return
      travelSegments.push({
        mode: String(segment.mode),
        travel_class: String(segment.travel_class ?? 'economy'),
        attendees: Number(segment.attendees ?? 0),
        distance_km: Number(segment.distance_km ?? 0),
        label: typeof segment.label === 'string' ? segment.label : '',
      })
    })

    nextDraft.travel_segments = travelSegments
  }
  return nextDraft
}

export function financialPresetFromScenario(scenario: Scenario): Partial<FinancialCalcState> {
  const payload = scenario.input_payload
  const attendees = scenario.attendees || 0
  const days = scenario.event_days || 1
  const renewablePct = Number(payload?.venue_energy?.renewable_pct ?? 0)
  const proxyKwh = attendees * 2 * days * 30
  const energy_kwh = Math.round(proxyKwh * (1 - renewablePct / 100))

  const cateringType = String(payload?.catering?.catering_type ?? 'mixed_buffet')
  const switchPct = (
    {
      red_meat_meal: 0.6,
      seafood_meal: 0.4,
      mixed_buffet: 0.35,
      vegetarian_meal: 0,
      vegan_meal: 0,
    } as Record<string, number>
  )[cateringType] ?? 0.3

  return {
    baseline: scenario.emissions.total_tco2e,
    energy_kwh,
    meal_switches: Math.round(attendees * days * 2 * switchPct),
    linked_scenario_id: scenario.scenario_id,
    linked_scenario_name: scenario.name,
  }
}

export function buildFlowDiagram(scenario: Scenario | null): string {
  if (!scenario) return ''

  const emissionRows = EMISSION_CATEGORIES.map((category) => ({
    ...category,
    value: Number(scenario.emissions[category.key as keyof typeof scenario.emissions] ?? 0),
  })).filter((row) => row.value > 0)

  const scopes = scenario.emissions.scopes
  let diagram = 'flowchart TD\n'
  diagram += `  EVT["${scenario.name}\\n${scenario.attendees} attendees · ${scenario.event_days} days"]\n`

  emissionRows.forEach((row) => {
    diagram += `  ${row.key.toUpperCase()}["${row.label}\\n${row.value.toFixed(3)} tCO2e"]\n`
  })

  if (scopes) {
    diagram += `  S1["Scope 1\\n${scopes.scope1_tco2e.toFixed(3)} t"]\n`
    diagram += `  S2["Scope 2\\n${scopes.scope2_tco2e.toFixed(3)} t"]\n`
    diagram += `  S3["Scope 3\\n${scopes.scope3_tco2e.toFixed(3)} t"]\n`
  }

  diagram += `  TOT(["Total\\n${scenario.emissions.total_tco2e.toFixed(3)} tCO2e"])\n`

  emissionRows.forEach((row) => {
    diagram += `  EVT --> ${row.key.toUpperCase()}\n`
  })

  emissionRows.forEach((row) => {
    const target =
      row.key === 'venue_energy_tco2e'
        ? 'S2'
        : row.key === 'equipment_tco2e'
          ? 'TOT'
          : 'S3'
    diagram += `  ${row.key.toUpperCase()} --> ${target}\n`
  })

  if (scopes) {
    diagram += '  S1 --> TOT\n'
    diagram += '  S2 --> TOT\n'
    diagram += '  S3 --> TOT\n'
  }

  diagram += '  style EVT fill:#12372a,stroke:#0b281d,color:#ffffff\n'
  diagram += '  style TOT fill:#1d7a5a,stroke:#145640,color:#ffffff\n'
  if (scopes) {
    diagram += '  style S1 fill:#fee2e2,stroke:#ef4444,color:#7f1d1d\n'
    diagram += '  style S2 fill:#fef3c7,stroke:#f59e0b,color:#78350f\n'
    diagram += '  style S3 fill:#ccfbf1,stroke:#14b8a6,color:#134e4a\n'
  }
  emissionRows.forEach((row) => {
    diagram += `  style ${row.key.toUpperCase()} fill:${row.color}33,stroke:${row.color},color:#08281f\n`
  })
  return diagram
}
