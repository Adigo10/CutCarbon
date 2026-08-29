export type TabId =
  | 'dashboard'
  | 'chat'
  | 'scenarios'
  | 'financial'
  | 'offsets'
  | 'compliance'
  | 'data'

export type AuthMode = 'login' | 'register'

export interface NavItem {
  id: TabId
  label: string
  description: string
  accent: string
}

export interface UserOut {
  id: string
  email: string
  created_at: string
  is_admin: boolean
}

export interface TravelSegment {
  mode: string
  travel_class: string
  attendees: number
  /** One-way distance for the leg; doubled by the engine when round_trip is true. */
  distance_km: number
  round_trip?: boolean
  label?: string
}

export interface VenueEnergyPayload {
  grid_region: string
  renewable_pct: number
}

export interface AccommodationPayload {
  accommodation_type: string
  room_nights: number
}

export interface CateringPayload {
  catering_type: string
  meals: number
  include_beverages: boolean
  include_alcohol: boolean
  coffee_tea_cups?: number
}

export interface EquipmentPayload {
  stage_m2: number
  lighting_days: number
  sound_system_days: number
  led_screen_m2: number
  projectors: number
  generator_hours: number
  freight_tonne_km: number
}

export interface SwagPayload {
  tshirts: number
  tshirt_type: string
  tote_bags: number
  lanyards: number
  badges: number
  badge_type: string
  notebooks: number
  water_bottles: number
}

export interface DigitalPayload {
  virtual_attendees: number
  streaming_hours_per_day: number
  livestream_production_hours?: number
  event_app_users?: number
  emails_sent?: number
}

export interface ScenarioInputPayload {
  name: string
  event_name: string
  event_type: string
  location: string
  attendees: number
  event_days: number
  mode: string
  travel_segments: TravelSegment[]
  venue_energy?: VenueEnergyPayload
  accommodation?: AccommodationPayload
  catering?: CateringPayload
  equipment?: EquipmentPayload
  swag?: SwagPayload
  digital?: DigitalPayload
}

export interface ScopeBreakdown {
  scope1_tco2e: number
  scope2_tco2e: number
  scope3_tco2e: number
}

// Data-quality tiers, coarsest first. `primary` is an evidence tier — the backend
// awards it only when supporting documents are attached, never for form
// completeness — so it can arrive from the API but is never inferred here.
export type DataQualityTier = 'modelled' | 'partly_primary' | 'primary'

export const DATA_QUALITY_LABELS: Record<DataQualityTier, string> = {
  modelled: 'Tier 3 — modelled',
  partly_primary: 'Tier 2 — partly primary',
  primary: 'Tier 1 — primary (evidenced)',
}

export interface Emissions {
  travel_tco2e: number
  venue_energy_tco2e: number
  accommodation_tco2e: number
  catering_tco2e: number
  materials_waste_tco2e: number
  equipment_tco2e: number
  swag_tco2e: number
  digital_tco2e: number
  total_tco2e: number
  per_attendee_tco2e: number
  per_attendee_day_tco2e: number
  data_quality: DataQualityTier
  scopes?: ScopeBreakdown
}

export interface BenchmarkComparison {
  event_type: string
  your_per_attendee_day: number
  industry_typical: number
  industry_best_practice: number
  percentile_rank: string
  gap_to_best_practice_pct: number
}

export interface FactorSnapshot {
  [key: string]: unknown
  captured_at?: string
  ef_version?: string
  engine_version?: string
  venue_grid_region?: string
  travel_long_haul_economy_kg_per_pkm?: number
  travel_short_haul_economy_kg_per_pkm?: number
  travel_car_petrol_kg_per_pkm?: number
  venue_grid_kg_per_kwh?: number
  catering_kg_per_meal?: number
  catering_type?: string
  accommodation_kg_per_room_night?: number
  waste_landfill_kg_per_kg?: number
}

export interface Scenario {
  scenario_id: string
  name: string
  event_name: string
  location: string
  event_type: string
  attendees: number
  event_days: number
  emissions: Emissions
  assumptions: Record<string, unknown>
  input_payload?: ScenarioInputPayload
  factors_snapshot?: FactorSnapshot
  // Factor/engine drift: the versions a fresh calculation would use right now, and
  // whether this scenario's stored numbers predate them (recalculation available).
  current_ef_version?: string
  current_engine_version?: string
  factors_stale?: boolean
  benchmark?: BenchmarkComparison | null
  created_at: string
}

export interface ReductionSuggestion {
  action: string
  label: string
  co2e_saved_tco2e: number
  estimated_cost_usd: number
  category: string
  difficulty: string
  scope: number | string
  is_neutralization?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  extracted_data?: Record<string, unknown>
  financial_analysis?: FinancialResult
}

export interface ChatResponse {
  reply: string
  extracted_data?: Record<string, unknown> | null
  suggestions: string[]
  session_id?: string
  financial_analysis?: FinancialResult | null
}

export interface FinancialCalcState {
  region: string
  baseline: number
  reduction_pct: number
  energy_kwh: number
  meal_switches: number
  attendees: number
  actions: string[]
  covered_by_carbon_pricing: boolean
  internal_carbon_price_usd: number
  linked_scenario_id: string | null
  linked_scenario_name: string | null
}

export interface TaxSaving {
  scheme: string
  savings_usd: number
  savings_local: number
  currency: string
  description: string
}

export interface FinancialResult {
  total_co2e_reduced: number
  carbon_tax_savings: TaxSaving[]
  energy_cost_savings_usd: number
  catering_cost_savings_usd: number
  available_incentives: Array<Record<string, unknown>>
  total_financial_savings_usd: number
  co2e_reduction_pct: number
  roi_months?: number | null
  compliance_value_usd: number
  carbon_price_basis?: 'statutory' | 'internal'
  internal_carbon_price_usd?: number | null
  internal_carbon_value_usd?: number
  notes?: string[]
}

export interface OffsetProject {
  label: string
  icon: string
  description: string
  avg_price_usd: number
  price_range: [number, number]
  permanence: string
  additionality_risk: string
  co_benefits: string[]
  sdgs: number[]
  registries: string[]
}

export interface OffsetRegistry {
  name: string
  url: string
  credibility: string
  description: string
}

export interface OffsetPurchase {
  id: number
  scenario_id?: string | null
  project_type: string
  registry: string
  quantity_tco2e: number
  price_per_tco2e_usd: number
  total_cost_usd: number
  vintage_year: number
  serial_number?: string | null
  status: string
  retired_at?: string | null
  notes?: string | null
  created_at: string
  // Credit-integrity evidence (ICVCM CCP / Article 6.4 + registry retirement).
  ccp_approved?: boolean | null
  article6_adjustment?: boolean | null
  methodology?: string | null
  retirement_serial?: string | null
  retirement_date?: string | null
  country?: string | null
  claim_eligible: boolean
  vintage_stale: boolean
}

export interface OffsetPortfolioSummary {
  total_purchased_tco2e: number
  total_retired_tco2e: number
  total_cost_usd: number
  by_project_type: Record<string, number>
  by_registry: Record<string, number>
  coverage_pct?: number | null
  // Compliant measured/reduced/residual-compensated wording; empty when no
  // scenario is in scope. Never render coverage % as a neutrality claim.
  claim_statement?: string
}

export interface OffsetRecommendation {
  project_type: string
  label: string
  description: string
  avg_price_usd: number
  recommended_qty_tco2e: number
  estimated_cost_usd: number
  permanence: string
  additionality_risk?: string
  risk_warning?: string
  co_benefits: string[]
  sdgs: number[]
  basis?: 'gross' | 'net_of_reductions'
  residual_tco2e?: number
}

export interface NewOffsetPurchase {
  project_type: string
  registry: string
  quantity_tco2e: number
  price_per_tco2e_usd: number
  vintage_year: number
  notes: string
  ccp_approved: boolean
  article6_adjustment: boolean
  methodology: string
  retirement_serial: string
  retirement_date: string
  country: string
}

export interface ComplianceInput {
  region: string
  total_tco2e: number
  attendees: number
  event_days: number
  has_scope3: boolean
  has_ghg_report: boolean
}

export interface ComplianceCheck {
  framework: string
  status: string
  score_pct: number
  gaps: string[]
  recommendations: string[]
}

export interface ComplianceReport {
  overall_score_pct: number
  checks: ComplianceCheck[]
  mandatory_frameworks: string[]
  penalty_risk_usd: number
}

export interface ReportDownloadOptions {
  region?: string
  has_scope3?: boolean
  has_ghg_report?: boolean
}

export type ScenarioReportFormat = 'json' | 'csv' | 'xlsx' | 'pdf'

export interface AgentStatus {
  name: string
  category: string
  url: string
  goal_preview: string
  ttl_hours: number
  last_run?: string | null
  last_status?: string | null
  cache_valid: boolean
  run_id?: string | null
}

export interface AgentRun {
  id: number
  agent_name: string
  category: string
  status: string
  run_id?: string | null
  num_steps?: number | null
  source_url?: string | null
  fetched_at: string
  error?: string | null
  data?: Record<string, unknown> | null
}

export interface OffsetMarket {
  [key: string]: string | number | boolean | undefined
}

export interface Toast {
  id: number
  tone: 'neutral' | 'success' | 'warning' | 'danger'
  message: string
}

export interface ScenarioDraft {
  name: string
  event_type: string
  attendees: number
  event_days: number
  location: string
  venue_grid: string
  catering_type: string
  include_alcohol: boolean
  accommodation_type: string
  renewable_pct: number
  travel_segments: TravelSegment[]
  stage_m2: number
  lighting_days: number
  sound_system_days: number
  led_screen_m2: number
  generator_hours: number
  tshirts: number
  tshirt_type: string
  tote_bags: number
  lanyards: number
  badges: number
  virtual_attendees: number
  streaming_hours_per_day: number
  event_app_users: number
  emails_sent: number
}
