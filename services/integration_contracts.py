"""Versioned collaboration DTOs, not Track 3–5 logic or an approval authority."""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from services.calculations import D, anniversary, cents
from services.models import StrictModel


class ContractPeriod(StrictModel):
    start_year: int = Field(ge=1900, le=2200)
    start_date: date | None = None
    base_years: int = Field(ge=1, le=20)
    option_years: int = Field(ge=0, le=20)
    period_basis: Literal["exact date", "illustrative annual boundaries"]
    currency: Literal["SGD"] = "SGD"

    @model_validator(mode="after")
    def consistent_period(self):
        if self.base_years + self.option_years > 20:
            raise ValueError("Contract cannot exceed 20 years")
        if self.start_date and self.start_date.year != self.start_year:
            raise ValueError("Start date and year disagree")
        if (self.start_date is not None) != (self.period_basis == "exact date"):
            raise ValueError("Period basis must disclose exact versus illustrative boundaries")
        return self


class EvidenceReference(StrictModel):
    evidence_id: str = Field(min_length=1)
    kind: Literal["synthetic fixture", "officer assumption", "validated tender evidence"]
    label: str = Field(min_length=1)
    record_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AssumptionReference(StrictModel):
    assumption_id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class RoleYearAmount(StrictModel):
    contract_year: int = Field(ge=1, le=20)
    pricing_year: int = Field(ge=1900, le=2200)
    period_start: date
    period_end: date
    optional: bool
    quantity: float = Field(gt=0, le=10000)
    monthly_unit_rate: float = Field(gt=0)
    annual_adjustment: float = Field(
        default=0,
        ge=0,
        description="Separately evidenced annual policy/component addition; not a trade-cost allowance",
    )
    annual_cost: float = Field(ge=0)

    @model_validator(mode="after")
    def reconciled_amount(self):
        expected = cents(
            D(cents(D(self.quantity) * D(self.monthly_unit_rate) * 12)) + D(self.annual_adjustment)
        )
        if D(self.annual_cost) != D(expected):
            raise ValueError(
                "Annual cost must reconcile to quantity × monthly rate × 12 plus disclosed adjustment"
            )
        if self.period_end < self.period_start:
            raise ValueError("Annual period ends before it starts")
        return self


class PricedRole(StrictModel):
    role_id: str = Field(min_length=1, max_length=80)
    original_title: str = Field(min_length=1, max_length=160)
    mapped_benchmark_role: str | None = None
    matched_budget_role_id: str | None = None
    responsibility_ids: list[str] = Field(default_factory=list)
    duties: str = ""
    quantity: float = Field(gt=0, le=10000)
    quantity_unit: Literal["headcount", "FTE"]
    quantity_basis: str = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    rate_unit: Literal["inclusive monthly per head", "inclusive monthly per FTE"]
    source_rate_basis: str = Field(min_length=1)
    rate_pricing_year: int = Field(ge=1900, le=2200)
    evidence_refs: list[str] = Field(min_length=1)
    assumption_refs: list[str] = Field(min_length=1)
    years: list[RoleYearAmount] = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_units(self):
        expected_unit = (
            "inclusive monthly per head" if self.quantity_unit == "headcount" else "inclusive monthly per FTE"
        )
        if self.rate_unit != expected_unit:
            raise ValueError("Rate unit must match the explicit quantity unit; conversion cannot be inferred")
        if self.quantity_unit == "headcount" and any(
            not float(q).is_integer() for q in [self.quantity, *(y.quantity for y in self.years)]
        ):
            raise ValueError("Fractional quantities require FTE")
        return self


class ExcludedRole(StrictModel):
    role_id: str = Field(min_length=1)
    original_title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    proposed_quantity: Literal[0] = 0


class YearTotal(StrictModel):
    contract_year: int = Field(ge=1, le=20)
    amount: float = Field(ge=0)


class CostDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    synthetic: bool
    label: str = Field(min_length=1)
    revision: int = Field(ge=1)
    contract: ContractPeriod
    roles: list[PricedRole] = Field(min_length=1)
    excluded_roles: list[ExcludedRole] = Field(default_factory=list)
    assumptions: list[AssumptionReference] = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    annual_totals: list[YearTotal] = Field(min_length=1)
    base_total: float = Field(ge=0)
    option_total: float = Field(ge=0)
    contract_total: float = Field(ge=0)

    @model_validator(mode="after")
    def consistent_document(self):
        def unique(values, label):
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label}")

        unique([r.role_id for r in self.roles] + [r.role_id for r in self.excluded_roles], "role identifiers")
        unique([e.evidence_id for e in self.evidence], "evidence identifiers")
        unique([a.assumption_id for a in self.assumptions], "assumption identifiers")
        evidence_ids = {e.evidence_id for e in self.evidence}
        assumption_ids = {a.assumption_id for a in self.assumptions}
        years = self.contract.base_years + self.contract.option_years
        expected = list(range(1, years + 1))
        for role in self.roles:
            if not set(role.evidence_refs) <= evidence_ids or not set(role.assumption_refs) <= assumption_ids:
                raise ValueError("Role references unknown evidence or assumptions")
            if [y.contract_year for y in role.years] != expected:
                raise ValueError("Every role requires each contract year exactly once, in order")
            if D(role.years[0].quantity) != D(role.quantity) or D(role.years[0].monthly_unit_rate) != D(
                role.monthly_rate
            ):
                raise ValueError("Year 1 quantity and rate must match the role's base selections")
            for row in role.years:
                if row.pricing_year != self.contract.start_year + row.contract_year - 1:
                    raise ValueError("Pricing year differs from the annual contract boundary year")
                if row.optional != (row.contract_year > self.contract.base_years):
                    raise ValueError("Base/option marker disagrees with contract period")
                start = self.contract.start_date or date(self.contract.start_year, 1, 1)
                if row.period_start != anniversary(
                    start, row.contract_year - 1
                ) or row.period_end != anniversary(start, row.contract_year) - timedelta(days=1):
                    raise ValueError("Annual dates disagree with the disclosed contract boundaries")
        if [y.contract_year for y in self.annual_totals] != expected:
            raise ValueError("Annual totals must cover every contract year in order")
        totals = [cents(sum(D(r.years[i].annual_cost) for r in self.roles)) for i in range(years)]
        if [D(y.amount) for y in self.annual_totals] != list(map(D, totals)):
            raise ValueError("Annual totals do not reconcile to role/year rows")
        base = cents(sum(map(D, totals[: self.contract.base_years])))
        option = cents(sum(map(D, totals[self.contract.base_years :])))
        if (D(self.base_total), D(self.option_total), D(self.contract_total)) != (
            D(base),
            D(option),
            D(cents(D(base) + D(option))),
        ):
            raise ValueError("Base/option/full totals do not reconcile")
        if self.synthetic and "synthetic" not in self.label.casefold():
            raise ValueError("Synthetic documents require a visible synthetic label")
        return self


class ApprovalReference(StrictModel):
    actor: str = Field(min_length=1)
    approved_at: datetime
    approval_reference: str = Field(min_length=1)
    synthetic_approval: bool


class BudgetDocument(CostDocument):
    document_type: Literal["manpower_budget"] = "manpower_budget"
    budget_id: str = Field(min_length=1)
    source_plan_id: str = Field(min_length=1)
    source_plan_version: int = Field(ge=1)
    status: Literal["draft", "submitted", "approved"]
    approval: ApprovalReference | None = None

    @model_validator(mode="after")
    def approval_state(self):
        if (self.status == "approved") != (self.approval is not None):
            raise ValueError(
                "Only approved budgets carry approval metadata; drafts/submitted budgets are not approved"
            )
        if self.approval and self.approval.synthetic_approval != self.synthetic:
            raise ValueError("Synthetic approval cannot be used as a real approval")
        return self


class TenderSubmission(CostDocument):
    document_type: Literal["tender_submission"] = "tender_submission"
    submission_id: str = Field(min_length=1)
    tender_id: str = Field(min_length=1)
    tenderer_id: str = Field(min_length=1)
    budget_id: str = Field(min_length=1)
    budget_revision: int = Field(ge=1)
    status: Literal["draft", "submitted"]
    submitted_at: datetime | None = None

    @model_validator(mode="after")
    def submission_state(self):
        if self.status == "submitted" and self.submitted_at is None:
            raise ValueError("A submitted tender requires its submission timestamp")
        return self
