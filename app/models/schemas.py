from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import uuid4


# -- Enums ---------------------------------------------------------------------

class TravelMode(str, Enum):
    SHORT_HAUL_FLIGHT = "short_haul_flight"
    LONG_HAUL_FLIGHT = "long_haul_flight"
    PRIVATE_JET = "private_jet"
    TRAIN_EUROPE = "train_europe"
    TRAIN_UK = "train_uk"
    TRAIN_ASIA = "train_asia"
    TRAIN_HIGH_SPEED = "train_high_speed"
    CAR_PETROL = "car_petrol"
    CAR_DIESEL = "car_diesel"
    CAR_HYBRID = "car_hybrid"
    CAR_EV = "car_ev"
    BUS_COACH = "bus_coach"
    SHUTTLE_BUS = "shuttle_bus"
    MRT_METRO = "mrt_metro"
    TAXI_RIDESHARE = "taxi_rideshare"
    FERRY = "ferry"
    E_SCOOTER = "e_scooter"
    CYCLING = "cycling"


class TravelClass(str, Enum):
    ECONOMY = "economy"
    BUSINESS = "business"
    FIRST = "first"


class AccommodationType(str, Enum):
    BUDGET = "budget_hotel"
    STANDARD = "standard_hotel"
    LUXURY = "luxury_hotel"
    RESORT = "resort"
    ECO_LODGE = "eco_lodge"
    SERVICED = "serviced_apartment"
    AIRBNB = "airbnb_shared"
    HOSTEL = "hostel"
    NONE = "no_accommodation"


class CateringType(str, Enum):
    RED_MEAT = "red_meat_meal"
    WHITE_MEAT = "white_meat_meal"
    SEAFOOD = "seafood_meal"
    VEGETARIAN = "vegetarian_meal"
    VEGAN = "vegan_meal"
    MIXED = "mixed_buffet"
    LOCAL_ORGANIC = "local_organic"
    FINGER_FOOD = "finger_food"


class GridRegion(str, Enum):
    SINGAPORE = "singapore"
    EU = "eu_average"
    UK = "uk"
    AUSTRALIA = "australia"
    USA = "usa"
    CHINA = "china"
    INDIA = "india"
    JAPAN = "japan"
    SOUTH_KOREA = "south_korea"
    CANADA = "canada"
    BRAZIL = "brazil"
    UAE = "uae"
    SOUTH_AFRICA = "south_africa"
    GERMANY = "germany"
    FRANCE = "france"
    NORDICS = "nordics"
    GLOBAL = "global_average"


class ScenarioMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


class EventType(str, Enum):
    CONFERENCE = "conference"
    TRADE_SHOW = "trade_show"
    GALA_DINNER = "gala_dinner"
    MUSIC_FESTIVAL = "music_festival"
    CORPORATE_MEETING = "corporate_meeting"
    SPORTING_EVENT = "sporting_event"
    VIRTUAL_EVENT = "virtual_event"
    HYBRID_EVENT = "hybrid_event"
    WEDDING = "wedding"


class OffsetProjectType(str, Enum):
    RENEWABLE_ENERGY = "renewable_energy"
    FORESTRY = "forestry_afforestation"
    REDD_PLUS = "redd_plus"
    COOKSTOVE = "cookstove"
    METHANE_CAPTURE = "methane_capture"
    BLUE_CARBON = "blue_carbon"
    DIRECT_AIR_CAPTURE = "direct_air_capture"
    BIOCHAR = "biochar"
    ENHANCED_WEATHERING = "enhanced_weathering"
    COMMUNITY_ENERGY = "community_energy"


class OffsetStatus(str, Enum):
    PURCHASED = "purchased"
    RETIRED = "retired"
    CANCELLED = "cancelled"


# -- Input models --------------------------------------------------------------

class TravelSegment(BaseModel):
    mode: TravelMode
    travel_class: TravelClass = TravelClass.ECONOMY
    attendees: int
    distance_km: float
    label: str = ""


class VenueEnergy(BaseModel):
    grid_region: GridRegion = GridRegion.GLOBAL
    kwh_consumed: Optional[float] = None
    venue_area_m2: Optional[float] = None
    event_days: int = 1
    renewable_pct: float = 0.0  # 0-100


class AccommodationGroup(BaseModel):
    accommodation_type: AccommodationType = AccommodationType.STANDARD
    room_nights: int
    attendees_sharing: float = 1.5  # avg attendees per room


class CateringGroup(BaseModel):
    catering_type: CateringType = CateringType.MIXED
    meals: int
    include_beverages: bool = True
    include_alcohol: bool = False
    coffee_tea_cups: int = 0


class WasteGroup(BaseModel):
    general_waste_kg: float = 0.0
    recycled_kg: float = 0.0
    composted_kg: float = 0.0
    printed_materials_per_attendee: bool = True
    exhibition_booths_m2: float = 0.0


class EquipmentGroup(BaseModel):
    stage_m2: float = 0.0
    lighting_days: int = 0
    sound_system_days: int = 0
    led_screen_m2: float = 0.0
    projectors: int = 0
    generator_hours: float = 0.0
    freight_tonne_km: float = 0.0


class SwagGroup(BaseModel):
    tshirts: int = 0
    tshirt_type: str = "cotton"  # cotton | organic | recycled
    tote_bags: int = 0
    lanyards: int = 0
    badges: int = 0
    badge_type: str = "plastic"  # plastic | recycled
    notebooks: int = 0
    water_bottles: int = 0


class EventScenarioInput(BaseModel):
    name: str
    event_name: str = "My Event"
    event_type: EventType = EventType.CONFERENCE
    location: str = "Singapore"
    attendees: int
    event_days: int = 1
    mode: ScenarioMode = ScenarioMode.BASIC
    travel_segments: List[TravelSegment] = Field(default_factory=list)
    venue_energy: Optional[VenueEnergy] = None
    accommodation: Optional[AccommodationGroup] = None
    catering: Optional[CateringGroup] = None
    waste: Optional[WasteGroup] = None
    equipment: Optional[EquipmentGroup] = None
    swag: Optional[SwagGroup] = None


# -- Output / result models ----------------------------------------------------

class ScopeBreakdown(BaseModel):
    scope1_tco2e: float = 0.0  # Direct (generators, owned vehicles)
    scope2_tco2e: float = 0.0  # Purchased energy (venue electricity)
    scope3_tco2e: float = 0.0  # All other indirect (travel, catering, waste, accommodation)


class EmissionBreakdown(BaseModel):
    travel_tco2e: float = 0.0
    venue_energy_tco2e: float = 0.0
    accommodation_tco2e: float = 0.0
    catering_tco2e: float = 0.0
    materials_waste_tco2e: float = 0.0
    equipment_tco2e: float = 0.0
    swag_tco2e: float = 0.0
    total_tco2e: float = 0.0
    per_attendee_tco2e: float = 0.0
    per_attendee_day_tco2e: float = 0.0
    data_quality: str = "estimated"  # estimated | partial | verified
    scopes: Optional[ScopeBreakdown] = None


class BenchmarkComparison(BaseModel):
    event_type: str
    your_per_attendee_day: float
    industry_typical: float
    industry_best_practice: float
    percentile_rank: str  # "above average" | "average" | "below average" | "best practice"
    gap_to_best_practice_pct: float


class ScenarioResult(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    event_name: str
    location: str = ""
    event_type: str = "conference"
    attendees: int
    event_days: int
    emissions: EmissionBreakdown
    benchmark: Optional[BenchmarkComparison] = None
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


# -- Chat models ---------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    event_context: Optional[Dict[str, Any]] = None
    scenario_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    extracted_data: Optional[Dict[str, Any]] = None
    updated_scenario: Optional[EventScenarioInput] = None
    suggestions: List[str] = Field(default_factory=list)


# -- Financial models ----------------------------------------------------------

class FinancialRequest(BaseModel):
    scenario_id: Optional[str] = None
    baseline_tco2e: float
    reduced_tco2e: float
    region: str = "singapore"
    energy_kwh_saved: float = 0.0
    meal_switches: int = 0
    attendees: int = 0
    actions_taken: List[str] = Field(default_factory=list)


class TaxSaving(BaseModel):
    scheme: str
    savings_usd: float
    savings_local: float
    currency: str
    description: str


class FinancialResult(BaseModel):
    total_co2e_reduced: float
    carbon_tax_savings: List[TaxSaving]
    energy_cost_savings_usd: float
    catering_cost_savings_usd: float
    available_incentives: List[Dict[str, Any]]
    total_financial_savings_usd: float
    co2e_reduction_pct: float
    roi_months: Optional[float] = None
    compliance_value_usd: float = 0.0


# -- Compliance models ---------------------------------------------------------

class ComplianceRequest(BaseModel):
    total_tco2e: float
    has_scope3: bool = True
    has_ghg_report: bool = False
    region: str = "singapore"
    event_days: int = 1
    attendees: int = 100


class ComplianceCheck(BaseModel):
    framework: str
    status: str  # compliant | partial | non_compliant | not_applicable
    score_pct: float
    gaps: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    overall_score_pct: float
    checks: List[ComplianceCheck]
    mandatory_frameworks: List[str]
    penalty_risk_usd: float


# -- Carbon Offset models ------------------------------------------------------

class OffsetPurchaseCreate(BaseModel):
    scenario_id: Optional[str] = None
    project_type: OffsetProjectType
    registry: str = "gold_standard"
    quantity_tco2e: float
    price_per_tco2e_usd: float
    vintage_year: int = 2025
    serial_number: Optional[str] = None
    notes: Optional[str] = None


class OffsetPurchaseOut(BaseModel):
    id: int
    scenario_id: Optional[str]
    project_type: str
    registry: str
    quantity_tco2e: float
    price_per_tco2e_usd: float
    total_cost_usd: float
    vintage_year: int
    serial_number: Optional[str]
    status: str
    retired_at: Optional[str]
    notes: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class OffsetPortfolioSummary(BaseModel):
    total_purchased_tco2e: float
    total_retired_tco2e: float
    total_cost_usd: float
    by_project_type: Dict[str, float] = Field(default_factory=dict)
    by_registry: Dict[str, float] = Field(default_factory=dict)
    coverage_pct: Optional[float] = None  # vs a scenario's total emissions


class OffsetRecommendation(BaseModel):
    project_type: str
    label: str
    description: str
    avg_price_usd: float
    recommended_qty_tco2e: float
    estimated_cost_usd: float
    permanence: str
    co_benefits: List[str]
    sdgs: List[int]


class ScenarioReportMetric(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "tCO2e"
    pct_total: Optional[float] = None


class ScenarioComplianceOverrides(BaseModel):
    region: str = "singapore"
    has_scope3: bool = True
    has_ghg_report: bool = False


class ScenarioReportPayload(BaseModel):
    report_title: str
    exported_at: str = ""
    methodology: str = "GHG Protocol, ISO 14064-1"
    disclaimer: str = ""
    scenario: Dict[str, Any]
    categories: List[ScenarioReportMetric] = Field(default_factory=list)
    scope_breakdown: ScopeBreakdown
    benchmark: Optional[BenchmarkComparison] = None
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    factor_snapshot: Dict[str, Any] = Field(default_factory=dict)
    offset_portfolio: OffsetPortfolioSummary
    compliance: ComplianceReport
    compliance_overrides: ScenarioComplianceOverrides = Field(
        default_factory=ScenarioComplianceOverrides
    )


# -- Export models -------------------------------------------------------------

class ScenarioExport(BaseModel):
    scenario: Dict[str, Any]
    emissions_detail: Dict[str, Any]
    scope_breakdown: Optional[ScopeBreakdown] = None
    benchmark: Optional[BenchmarkComparison] = None
    assumptions: Dict[str, Any]
    methodology: str = "GHG Protocol, ISO 14064-1"
    exported_at: str = ""


# -- Auth schemas --------------------------------------------------------------

class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    created_at: str

    model_config = {"from_attributes": True}


class TokenWithUser(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
