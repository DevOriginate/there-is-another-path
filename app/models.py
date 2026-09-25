from __future__ import annotations

from typing import Dict, List, Literal, Optional
import re
from pydantic import BaseModel, Field, field_validator



_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_valid(candidate: str) -> bool:
    digits = [int(ch) for ch in candidate if ch.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        value = digit
        if i % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        checksum += value
    return checksum % 10 == 0


def validate_free_text(value: str) -> str:
    text = value or ""
    if _EMAIL_RE.search(text) or _SSN_RE.search(text):
        raise ValueError("Do not include email addresses, SSNs, account numbers, or other sensitive identifiers.")
    for match in _CARD_CANDIDATE_RE.finditer(text):
        if _luhn_valid(match.group(0)):
            raise ValueError("Do not include payment card numbers or other sensitive identifiers.")
    return text

class AssessmentInput(BaseModel):
    age_band: Literal['18-24','25-34','35-44','45-54','55-64','65+']
    current_situation: Literal['full_time_employee','part_time_employee','self_employed','freelancer','business_owner','student','unemployed','retired','between_careers','other']
    professional_direction: Literal['clear','idea_unsure','several_ideas','stuck','want_different','starting_over']
    primary_objectives: List[Literal['extra_income','new_career','start_business','work_for_myself','remote_work','leave_job_eventually','meaningful_work','use_experience_differently','learn_valuable_skill','rebuild_after_setback','dont_know']] = Field(min_length=1, max_length=2)
    financial_impact: Literal['250_month','500_month','1000_month','2500_month','replace_income','build_business_long_term','money_not_primary']
    available_capital: Literal['0','up_to_100','100_500','500_1500','1500_5000','5000_plus']
    income_urgency: Literal['asap','30_days','3_months','6_months','1_year','patient']
    risk_tolerance: Literal['almost_none','low','moderate','high','significant']
    weekly_time: Literal['lt3','3_5','5_10','10_20','20_40','40_plus']
    schedule: Literal['before_work','after_work','weekends','daytime','flexible','changes']
    learning_horizon: Literal['immediate','few_weeks','1_3_months','3_6_months','6_12_months','extensive']
    experience_years: Literal['none','lt2','2_5','5_10','10_20','20_30','30_plus']
    experience_areas: List[Literal['sales','customer_service','management','finance','technology','construction','healthcare','education','logistics','manufacturing','marketing','administration','hospitality','creative','legal','real_estate','transportation','retail','entrepreneurship','other','none']] = Field(default_factory=list)
    help_text: str = Field(default='', max_length=1000)
    natural_activities: List[Literal['talking','selling','teaching','writing','designing','building','repairing','numbers','technology','organizing','leading','researching','problem_solving','creating_content','negotiating','working_with_hands','helping_people','analyzing_information']] = Field(default_factory=list, max_length=5)
    forced_choices: Dict[str, Literal['customers','computer','build','sell','technical','people','create','improve']] = Field(default_factory=dict)
    work_location: Literal['fully_remote','mostly_remote','hybrid','in_person','outdoors','no_preference']
    economic_model_preference: Literal['stable_paycheck','freelancing','small_business','scalable_business','selling_products','selling_services','consulting','dont_know']
    sales_comfort: int = Field(ge=1, le=5)
    tech_comfort: int = Field(ge=1, le=5)
    visibility_comfort: int = Field(ge=1, le=5)
    constraints: List[Literal['full_time_job','dependents','limited_transportation','limited_startup_money','limited_computer_access','limited_internet','need_work_from_home','avoid_physical_work','none']] = Field(default_factory=list)
    prospecting: Literal['yes','maybe','online_only','prefer_not','absolutely_not']
    five_year_outcome: Literal['better_paying_career','work_independently','small_business','scalable_company','remote_anywhere','financial_stability','more_free_time','meaningful_work','semi_retirement','dont_know']
    primary_fear: Literal['losing_money','wasting_time','failing','starting_too_late','choosing_wrong','not_good_enough','giving_up_stability','others_think','dont_know_where_start']
    twelve_month_change: str = Field(default='', max_length=1500)

    @field_validator('help_text','twelve_month_change')
    @classmethod
    def reject_sensitive_free_text(cls, v):
        return validate_free_text(v)

    @field_validator('experience_areas')
    @classmethod
    def clean_experience_areas(cls, v):
        if 'none' in v and len(v) > 1:
            raise ValueError("'none' cannot be combined with other experience areas")
        return list(dict.fromkeys(v))

    @field_validator('primary_objectives','natural_activities','constraints')
    @classmethod
    def dedupe_lists(cls, v):
        return list(dict.fromkeys(v))

class PathResult(BaseModel):
    id: str
    name: str
    family: str
    score: float
    band: str
    personal_fit: float
    market_viability: float
    capability_fit: float
    experience_fit: float
    time_fit: float
    financial_fit: float
    work_style_fit: float
    risk_fit: float
    goal_fit: float
    learning_fit: float
    adjustments: List[str]
    strengths: List[str]
    constraints: List[str]
    first_move: str
    week_plan: List[str]

class AssessmentResult(BaseModel):
    confidence_score: int
    confidence_band: str
    conflicts: List[str]
    trait_profile: Dict[str, float]
    preference_profile: Dict[str, float]
    goal_profile: Dict[str, float]
    top_paths: List[PathResult]
    long_term_opportunity: Optional[PathResult] = None
    engine_version: str = '1.0.0'
    market_version: str = 'US-2026-Q3-initial'
