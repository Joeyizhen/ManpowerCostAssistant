"""Strict application contracts; unknown operational facts remain None."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> str:
    return datetime.now(UTC).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class Profile(StrictModel):
    name: str = "Untitled project"
    description: str = ""
    start: date | None = None
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    base_years: int | None = Field(default=None, ge=1, le=20)
    option_years: int | None = Field(default=None, ge=0, le=20)
    operational_type: str | None = None
    locations: str | None = None
    operating_hours: str | None = None
    critical_functions: str | None = None
    response_requirements: str | None = None
    assets: str | None = None
    exclusions: str = ""
    currency: Literal["SGD"] = "SGD"

    @property
    def costing_start(self):
        return self.start or (date(self.start_year, 1, 1) if self.start_year is not None else None)

    @property
    def period_basis(self):
        return (
            "Exact officer-supplied contract start date"
            if self.start
            else "Start year only; 1 January is an illustrative annual costing boundary, not a supplied start date. Exact dates are required for policies or calendar-year quotes."
        )

    @property
    def years(self) -> int:
        return (self.base_years or 0) + (self.option_years or 0)


class Responsibility(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    coverage: Literal["plan", "external", "not applicable", "unknown"] = "unknown"
    provider: str = ""
    evidence: str = "Officer input"


class Coverage(StrictModel):
    hours_per_day: float = Field(gt=0, le=24)
    days_per_week: int = Field(ge=1, le=7)
    simultaneous_posts: int = Field(ge=1, le=1000)
    capacity_hours: float = Field(gt=0, le=168)
    capacity_basis: Literal["gross", "net"]
    relief_factor: float = Field(ge=1, le=3)
    round_to_personnel: bool


class PolicyAdjustment(StrictModel):
    name: str = Field(min_length=1)
    effective_date: date
    annual_monthly_increment: float = Field(gt=0)
    affected_component: str = Field(min_length=1)
    source: str = Field(min_length=1)
    overlap_reviewed: bool = False
    basis_confirmed: bool = False
    # Increment is a monthly absolute amount per head, applied prospectively and prorated by month.


class Role(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    mapped_role: str | None = None
    mapping_reason: str = ""
    responsibility_ids: list[str] = Field(default_factory=list)
    included: bool = True
    exclusion_reason: str = ""
    experience: str = ""
    qualifications: str = ""
    quantity: float | None = Field(default=None, ge=0, le=10000)
    current_quantity: float | None = Field(default=None, ge=0, le=10000)
    quantity_unit: Literal["unspecified", "headcount", "FTE", "posts"] = "unspecified"
    quantity_basis: Literal["coverage", "officer scenario"] = "officer scenario"
    coverage: Coverage | None = None
    quantity_reason: str = ""
    duties_notes: str = ""
    deployment: Literal["unspecified", "dedicated", "shared / fractional", "mobile / relief"] = "unspecified"
    rate: float | None = Field(default=None, gt=0, le=10000000)
    rate_reason: str = ""
    rate_notes: str = ""
    rate_origin: Literal["Officer assumption", "Synthetic benchmark selection"] = "Officer assumption"
    rate_basis: Literal["inclusive monthly per head"] = "inclusive monthly per head"
    benchmark_status: Literal["awarded", "submitted", "both"] = "awarded"
    benchmark_year: int | None = Field(default=None, ge=1900, le=2200)
    benchmark_scope: str | None = None
    escalation: list[float] = Field(default_factory=list)
    escalation_reason: str = ""
    escalation_mode: Literal["assumption", "quoted schedule"] = "assumption"
    schedule_id: str | None = None
    yearly_quantities: list[float] = Field(default_factory=list)
    policies: list[PolicyAdjustment] = Field(default_factory=list)

    @field_validator("escalation")
    @classmethod
    def valid_escalation(cls, values):
        import math

        if any(not math.isfinite(v) or not -0.5 <= v <= 1 for v in values):
            raise ValueError("Escalation must be finite, between -50% and 100%")
        return values

    @field_validator("yearly_quantities")
    @classmethod
    def valid_quantities(cls, values):
        import math

        if any(not math.isfinite(v) or not 0 < v <= 10000 for v in values):
            raise ValueError("Yearly quantities must be finite and positive")
        return values


class Finding(StrictModel):
    id: str
    code: str
    role_id: str = ""
    year: int | None = None
    message: str
    impact: str
    blocking: bool = False
    status: Literal["resolved", "accepted exception", "unresolved risk", "data limitation"] = (
        "unresolved risk"
    )
    justification: str = "Officer justification was not provided."
    evidence: str = ""
    inclusion: str = ""
    officer: str = ""
    timestamp: str = Field(default_factory=now)
    further_approval: str = ""
    fingerprint: str = ""


class Plan(StrictModel):
    ui_step: int | None = Field(default=None, ge=0, le=5)
    input_steps_completed: list[int] = Field(default_factory=list)
    contract_kind: Literal["unspecified", "existing contract", "new site / service"] = "unspecified"
    current_deployment_status: Literal["known", "unavailable", "no existing deployment"] = "unavailable"
    input_support: str = ""
    manpower_review_requested: bool = False
    officer_manpower_input: list[dict] = Field(default_factory=list)
    id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    profile: Profile = Field(default_factory=Profile)
    responsibilities: list[Responsibility] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    confirmations: dict[str, int] = Field(default_factory=dict)
    decisions: dict[str, Finding] = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    chat: list[dict] = Field(default_factory=list)
    tool_audit: list[dict] = Field(default_factory=list)
    pending: list[dict] = Field(default_factory=list)
    working_notes: dict = Field(default_factory=dict)
    review_checkpoint: str = ""
    documents: list[dict] = Field(default_factory=list)
    final_officer: str = ""
    final_date: str = ""
    synthetic: bool = True


STAGES = [
    "Profile",
    "Responsibilities",
    "Quantities",
    "Manpower plan",
    "Rates",
    "Base-year overview",
    "Escalation",
    "Validation",
    "Contract budget",
    "Confirm & export",
]
GATES = ["profile", "responsibilities", "quantities", "plan", "rates", "base", "escalation", "validation"]
