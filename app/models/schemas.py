from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import uuid4


# ── Enums ──────────────────────────────────────────────────────────────────────

class TravelMode(str, Enum):
    SHORT_HAUL_FLIGHT = "short_haul_flight"
    LONG_HAUL_FLIGHT = "long_haul_flight"
    TRAIN_EUROPE = "train_europe"
    TRAIN_UK = "train_uk"
    TRAIN_ASIA = "train_asia"
    CAR_PETROL = "car_petrol"
    CAR_EV = "car_ev"
    BUS_COACH = "bus_coach"
    MRT_METRO = "mrt_metro"
    TAXI_RIDESHARE = "taxi_rideshare"


class TravelClass(str, Enum):
    ECONOMY = "economy"
    BUSINESS = "business"
    FIRST = "first"


class AccommodationType(str, Enum):
    BUDGET = "budget_hotel"
    STANDARD = "standard_hotel"
    LUXURY = "luxury_hotel"
    SERVICED = "serviced_apartment"
    AIRBNB = "airbnb_shared"


class CateringType(str, Enum):
    RED_MEAT = "red_meat_meal"
    WHITE_MEAT = "white_meat_meal"
    VEGETARIAN = "vegetarian_meal"
    VEGAN = "vegan_meal"
    MIXED = "mixed_buffet"


class GridRegion(str, Enum):
    SINGAPORE = "singapore"
    EU = "eu_average"
    UK = "uk"
    AUSTRALIA = "australia"
    USA = "usa"
    CHINA = "china"
    INDIA = "india"
    GLOBAL = "global_average"


class ScenarioMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


# ── Input models ───────────────────────────────────────────────────────────────

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


class WasteGroup(BaseModel):
    general_waste_kg: float = 0.0
    recycled_kg: float = 0.0
    composted_kg: float = 0.0
    printed_materials_per_attendee: bool = True
    exhibition_booths_m2: float = 0.0


class EventScenarioInput(BaseModel):
    name: str
    event_name: str = "My Event"
    location: str = "Singapore"
    attendees: int
    event_days: int = 1
    mode: ScenarioMode = ScenarioMode.BASIC
    travel_segments: List[TravelSegment] = []
    venue_energy: Optional[VenueEnergy] = None
    accommodation: Optional[AccommodationGroup] = None
    catering: Optional[CateringGroup] = None
    waste: Optional[WasteGroup] = None


# ── Output / result models ─────────────────────────────────────────────────────

class EmissionBreakdown(BaseModel):
    travel_tco2e: float = 0.0
    venue_energy_tco2e: float = 0.0
    accommodation_tco2e: float = 0.0
    catering_tco2e: float = 0.0
    materials_waste_tco2e: float = 0.0
    total_tco2e: float = 0.0
    per_attendee_tco2e: float = 0.0
    data_quality: str = "estimated"  # estimated | partial | verified


class ScenarioResult(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    event_name: str
    attendees: int
    event_days: int
    emissions: EmissionBreakdown
    assumptions: Dict[str, Any] = {}
    created_at: str = ""


# ── Chat models ────────────────────────────────────────────────────────────────

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
    suggestions: List[str] = []


# ── Financial models ───────────────────────────────────────────────────────────

class FinancialRequest(BaseModel):
    baseline_tco2e: float
    reduced_tco2e: float
    region: str = "singapore"
    energy_kwh_saved: float = 0.0
    meal_switches: int = 0
    attendees: int = 0
    actions_taken: List[str] = []


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


# ── Compliance models ──────────────────────────────────────────────────────────

class ComplianceCheck(BaseModel):
    framework: str
    status: str  # compliant | partial | non_compliant | not_applicable
    score_pct: float
    gaps: List[str] = []
    recommendations: List[str] = []


class ComplianceReport(BaseModel):
    overall_score_pct: float
    checks: List[ComplianceCheck]
    mandatory_frameworks: List[str]
    penalty_risk_usd: float
