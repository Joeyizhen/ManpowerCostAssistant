"""A review example with invented officer inputs. Loading it does not grant approvals."""

from datetime import date

from services.models import Coverage, Plan, Profile, Responsibility, Role


def demo_plan():
    plan = Plan(
        contract_kind="new site / service",
        current_deployment_status="no existing deployment",
        profile=Profile(
            name="Synthetic civic venue",
            description="Invented public venue with two buildings, events and tenant enquiries.",
            start=date(2024, 1, 1),
            base_years=4,
            option_years=2,
            operational_type="Public venue",
            locations="Two buildings on one site",
            operating_hours="Public opening 08:00–22:00 daily; technical duty 24/7",
            critical_functions="Technical response, contract oversight, event coordination, visitor enquiries",
            response_requirements="Officer assumption: technical on-site coverage at one simultaneous post",
            assets="Officer assumption: BMS present, chiller absent; other asset details unknown",
            exclusions="GST, specialist maintenance, security contract, cleaning, supplies and event delivery staff",
        ),
    )
    plan.responsibilities = [
        Responsibility(
            id="oversight", description="FM contract oversight and vendor coordination", coverage="plan"
        ),
        Responsibility(
            id="technical", description="One technical response post covered continuously", coverage="plan"
        ),
        Responsibility(id="events", description="Venue event coordination and bookings", coverage="plan"),
        Responsibility(
            id="security",
            description="Security guarding",
            coverage="external",
            provider="Separate security contractor",
        ),
        Responsibility(
            id="visitor", description="Visitor enquiries", coverage="external", provider="Internal venue team"
        ),
    ]
    plan.roles = [
        Role(
            id="fm",
            label="Facilities Manager",
            mapped_role="Facilities Manager",
            responsibility_ids=["oversight"],
            experience="Officer requirement: 5 years relevant experience",
            qualifications="Officer requirement: FM qualification",
            quantity=1,
            quantity_unit="headcount",
            quantity_reason="Officer-selected one-person scenario for oversight; workload rule unavailable",
            rate=8000,
            rate_reason="Synthetic comparable quote selection, inclusive manpower only",
            rate_origin="Synthetic benchmark selection",
            benchmark_year=2024,
            benchmark_scope="Public venue FM",
            escalation=[0, 0.025, 0.025, 0.025, 0.025, 0.025],
            escalation_reason="Officer scenario: constant 2.5% tender-price change; causes unknown",
        ),
        Role(
            id="tech",
            label="Technician",
            mapped_role="Technician",
            responsibility_ids=["technical"],
            experience="Officer requirement: 3 years technical response",
            qualifications="Officer requirement: relevant technical qualification",
            quantity=5,
            quantity_unit="headcount",
            quantity_basis="coverage",
            coverage=Coverage(
                hours_per_day=24,
                days_per_week=7,
                simultaneous_posts=1,
                capacity_hours=44,
                capacity_basis="gross",
                relief_factor=1.15,
                round_to_personnel=True,
            ),
            quantity_reason="Officer-confirmed illustrative 44 gross hours and 1.15 relief factor; round to dedicated personnel",
            rate=3900,
            rate_reason="Synthetic comparable quote selection; components unavailable",
            rate_origin="Synthetic benchmark selection",
            benchmark_year=2024,
            benchmark_scope="Public venue FM",
            escalation=[0, 0.03, 0.03, 0.03, 0.03, 0.03],
            escalation_reason="Officer scenario: constant 3% tender-price change; causes unknown",
        ),
        Role(
            id="events",
            label="Events Manager",
            responsibility_ids=["events"],
            experience="Officer requirement: event coordination experience",
            qualifications="Officer requirement: relevant coordination experience",
            quantity=1,
            quantity_unit="headcount",
            quantity_reason="Officer-selected scenario; no validated event workload rule",
            rate=5000,
            rate_reason="Invented officer rate assumption; no internal match or external research",
            escalation=[0, 0.02, 0.02, 0.02, 0.02, 0.02],
            escalation_reason="Officer-selected constant 2% scenario, no supporting schedule",
        ),
    ]
    plan.history.append(
        {"action": "Loaded labelled synthetic example; all stages require officer review", "version": 1}
    )
    return plan
