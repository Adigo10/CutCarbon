import type {
  ComplianceInput,
  FinancialCalcState,
  NavItem,
  NewOffsetPurchase,
  ScenarioDraft,
} from '../types'

export const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    description: 'Portfolio analytics, hotspot diagnostics, and scenario switching.',
    accent: 'var(--accent-fresh)',
  },
  {
    id: 'chat',
    label: 'AI Co-Pilot',
    description: 'Turn plain language into event assumptions and next-step analysis.',
    accent: 'var(--accent-cyan)',
  },
  {
    id: 'scenarios',
    label: 'Scenarios',
    description: 'Model event plans, edit inputs, and compare what-if pathways.',
    accent: 'var(--accent-amber)',
  },
  {
    id: 'financial',
    label: 'Financial',
    description: 'Translate emissions cuts into tax savings, incentives, and ROI.',
    accent: 'var(--accent-amber)',
  },
  {
    id: 'offsets',
    label: 'Offsets',
    description: 'Browse credit types, manage purchases, and retire residual emissions.',
    accent: 'var(--accent-lake)',
  },
  {
    id: 'compliance',
    label: 'Compliance',
    description: 'Check reporting readiness across GHG Protocol and regional regimes.',
    accent: 'var(--accent-rose)',
  },
  {
    id: 'data',
    label: 'Data & Exports',
    description: 'Download reports, inspect agent runs, and audit source freshness.',
    accent: 'var(--accent-slate)',
  },
]

export const START_SUGGESTIONS = [
  'Plan a 3-day tech conference in Singapore for 500 attendees with a hybrid option.',
  'Estimate emissions for 200 delegates flying from Europe to London for a summit.',
  'What happens if we switch our gala dinner from beef to vegetarian catering?',
]

export const QUICK_ACTIONS = [
  { title: 'Open AI Assistant', body: 'Capture event assumptions using natural language.' },
  { title: 'Build Baseline Scenario', body: 'Create a measurable baseline for comparisons.' },
  { title: 'Run Financial Model', body: 'Estimate tax exposure and incentive impact.' },
  { title: 'Plan Residual Offsets', body: 'Cover unavoidable emissions with verified credits.' },
]

export const EMISSION_CATEGORIES = [
  { key: 'travel_tco2e', label: 'Travel', color: '#1f6f6d' },
  { key: 'venue_energy_tco2e', label: 'Venue Energy', color: '#2f855a' },
  { key: 'accommodation_tco2e', label: 'Accommodation', color: '#8b6f47' },
  { key: 'catering_tco2e', label: 'Catering', color: '#9a4f4f' },
  { key: 'materials_waste_tco2e', label: 'Waste', color: '#5f6b84' },
  { key: 'equipment_tco2e', label: 'Equipment', color: '#3b6e8f' },
  { key: 'swag_tco2e', label: 'Swag', color: '#6e5c73' },
]

export const EVENT_TYPES = [
  ['conference', 'Conference'],
  ['trade_show', 'Trade Show'],
  ['gala_dinner', 'Gala Dinner'],
  ['music_festival', 'Music Festival'],
  ['corporate_meeting', 'Corporate Meeting'],
  ['sporting_event', 'Sporting Event'],
  ['virtual_event', 'Virtual Event'],
  ['hybrid_event', 'Hybrid Event'],
  ['wedding', 'Wedding'],
]

export const GRID_OPTIONS = [
  ['singapore', 'Singapore'],
  ['eu_average', 'EU Average'],
  ['uk', 'United Kingdom'],
  ['australia', 'Australia'],
  ['usa', 'United States'],
  ['japan', 'Japan'],
  ['south_korea', 'South Korea'],
  ['canada', 'Canada'],
  ['uae', 'UAE'],
  ['germany', 'Germany'],
  ['france', 'France'],
  ['nordics', 'Nordics'],
  ['global_average', 'Global Average'],
]

export const CATERING_OPTIONS = [
  ['mixed_buffet', 'Mixed Buffet'],
  ['red_meat_meal', 'Red Meat Heavy'],
  ['white_meat_meal', 'White Meat'],
  ['seafood_meal', 'Seafood'],
  ['vegetarian_meal', 'Vegetarian'],
  ['vegan_meal', 'Vegan'],
  ['local_organic', 'Local Organic'],
  ['finger_food', 'Finger Food'],
]

export const ACCOMMODATION_OPTIONS = [
  ['standard_hotel', 'Standard Hotel'],
  ['budget_hotel', 'Budget Hotel'],
  ['luxury_hotel', 'Luxury Hotel'],
  ['resort', 'Resort'],
  ['eco_lodge', 'Eco Lodge'],
  ['serviced_apartment', 'Serviced Apartment'],
  ['hostel', 'Hostel'],
  ['no_accommodation', 'No Accommodation'],
]

export const TSHIRT_OPTIONS = [
  ['cotton', 'Cotton'],
  ['organic', 'Organic'],
  ['recycled', 'Recycled'],
]

export const TRAVEL_MODE_OPTIONS = [
  ['short_haul_flight', 'Short-haul flight'],
  ['long_haul_flight', 'Long-haul flight'],
  ['private_jet', 'Private jet'],
  ['train_europe', 'Train Europe'],
  ['train_asia', 'Train Asia'],
  ['train_high_speed', 'High-speed rail'],
  ['car_petrol', 'Car (petrol)'],
  ['car_hybrid', 'Car (hybrid)'],
  ['car_ev', 'Car (EV)'],
  ['bus_coach', 'Coach'],
  ['shuttle_bus', 'Shuttle bus'],
  ['mrt_metro', 'Metro'],
  ['ferry', 'Ferry'],
  ['cycling', 'Cycling'],
]

export const TRAVEL_CLASS_OPTIONS = [
  ['economy', 'Economy'],
  ['business', 'Business'],
  ['first', 'First'],
]

export const FINANCIAL_REGIONS = [
  ['singapore', 'Singapore'],
  ['eu', 'European Union'],
  ['uk', 'United Kingdom'],
  ['australia', 'Australia'],
  ['usa', 'United States'],
  ['canada', 'Canada'],
  ['japan', 'Japan'],
]

export const AVAILABLE_ACTIONS = [
  { key: 'renewable_energy', label: 'Renewable energy' },
  { key: 'vegetarian_menu', label: 'Vegetarian menu' },
  { key: 'digital_materials', label: 'Digital materials' },
  { key: 'hybrid_event', label: 'Hybrid / virtual option' },
  { key: 'sustainable_swag', label: 'Sustainable swag' },
  { key: 'local_seasonal', label: 'Local seasonal catering' },
  { key: 'led_lighting', label: 'LED lighting upgrade' },
  { key: 'ghg_reporting', label: 'GHG reporting' },
  { key: 'carbon_audit', label: 'Carbon audit' },
  { key: 'sustainability_audit', label: 'Sustainability audit' },
  { key: 'carbon_offset', label: 'Carbon offset purchase' },
  { key: 'carbon_removal', label: 'Carbon removal purchase' },
]

export function createDefaultScenarioDraft(): ScenarioDraft {
  return {
    name: '',
    event_type: 'conference',
    attendees: 300,
    event_days: 2,
    location: 'Singapore',
    venue_grid: 'singapore',
    catering_type: 'mixed_buffet',
    include_alcohol: false,
    accommodation_type: 'standard_hotel',
    renewable_pct: 0,
    travel_segments: [],
    stage_m2: 0,
    lighting_days: 0,
    sound_system_days: 0,
    led_screen_m2: 0,
    generator_hours: 0,
    tshirts: 0,
    tshirt_type: 'cotton',
    tote_bags: 0,
    lanyards: 0,
    badges: 0,
  }
}

export function createDefaultFinancialCalc(): FinancialCalcState {
  return {
    region: 'singapore',
    baseline: 50,
    reduction_pct: 30,
    energy_kwh: 0,
    meal_switches: 0,
    actions: [],
    linked_scenario_id: null,
    linked_scenario_name: null,
  }
}

export function createDefaultComplianceInput(): ComplianceInput {
  return {
    region: 'singapore',
    total_tco2e: 50,
    attendees: 300,
    event_days: 2,
    has_scope3: true,
    has_ghg_report: false,
  }
}

export function createDefaultOffsetPurchase(): NewOffsetPurchase {
  return {
    project_type: 'renewable_energy',
    registry: 'gold_standard',
    quantity_tco2e: 1,
    price_per_tco2e_usd: 8.5,
    vintage_year: new Date().getFullYear(),
    notes: '',
  }
}
