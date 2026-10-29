"""Fully populated fictional project; preparation checkpoints are not final approval."""

from datetime import date

from services.models import Plan, Profile, PWMConfig, Responsibility, Role

EXAMPLE_NAME = "Appointment of FM Vendor to provide service for Site Xtown for 3 + 3 years (Example)"


def xtown_plan(records):
    from services.cost_routing import resolve_route
    from services.decision_basis import record_basis
    from services.pwm import catalog, get_schedule
    from services.workflow import confirm

    actor = "Example preparation (illustrative inputs, not officer approval)"
    plan = Plan(
        contract_kind="existing contract",
        current_deployment_status="known",
        profile=Profile(
            name=EXAMPLE_NAME,
            description="Example renewal for two commercial office blocks and a small retail podium at fictional Site Xtown. Additional occupied space increases administration, technical response and common-area cleaning workloads.",
            start=date(2027, 1, 1),
            base_years=3,
            option_years=3,
            operational_type="Commercial offices and retail podium",
            locations="Site Xtown: Block A, Block B and shared common areas",
            operating_hours="Office support Monday to Friday 08:00–18:00; retail common areas 07:00–22:00 daily",
            critical_functions="Vendor coordination, tenant administration, equipment response and common-area cleaning",
            response_requirements="Example deployment allowances for scheduled attendance and technical response; no validated staffing-adequacy standard is asserted",
            assets="Example BMS, lifts, ventilation, lighting and common-area equipment; specialist maintenance separately procured",
            exclusions="GST, security guarding, specialist maintenance, utilities, consumables and non-manpower costs",
        ),
    )
    specifications = [
        (
            "fm",
            "Facilities Manager",
            1,
            1,
            8000,
            "Contract oversight and vendor coordination",
            "Retain the existing management role for both office blocks",
        ),
        (
            "admin",
            "Admin Executive",
            1,
            2,
            3800,
            "Tenant requests, work orders and reporting",
            "Add one administrator for the additional occupied space and tenant requests",
        ),
        (
            "tech",
            "Technician",
            4,
            5,
            4200,
            "Scheduled technical rounds and equipment response",
            "Add one technician for the additional office wing and longer equipment-response roster",
        ),
        (
            "clean",
            "Cleaner",
            6,
            8,
            3400,
            "Indoor office and common-area cleaning",
            "Add two cleaners for the additional occupied office floors and common areas",
        ),
        (
            "clean-sup",
            "Cleaning Supervisor",
            1,
            1,
            5200,
            "Cleaning roster, inspection and team supervision",
            "Retain one supervisor for the combined cleaning team",
        ),
    ]
    for rid, title, current, proposed, rate, duty, reason in specifications:
        plan.responsibilities.append(Responsibility(id=rid, description=duty, coverage="plan"))
        role = Role(
            id=rid,
            label=title,
            mapped_role=title,
            current_quantity=current,
            quantity=proposed,
            quantity_unit="headcount",
            responsibility_ids=[rid],
            duties_notes=reason,
            quantity_reason="Example officer scenario: " + reason,
            experience="Example requirement: relevant experience in the stated duties",
            qualifications="Example requirement: relevant role qualifications to be verified before tender",
            rate=rate,
            rate_origin="Officer assumption",
            benchmark_year=2027,
            rate_reason="Illustrative inclusive monthly contractor allowance prepared for this example; not an observed market quote",
            escalation=[0] + [0.025] * 5,
            escalation_reason="Example officer assumption: constant 2.5% annual manpower cost allowance from Year 2; not an official wage forecast",
        )
        route = resolve_route(role)
        if route["route"] != "demonstration":
            role.future_routing = route
        if rid in ("clean", "clean-sup"):
            level = "General / indoor cleaner" if rid == "clean" else "Supervisor"
            schedule = next(
                s
                for s in catalog()["schedules"]
                if s["sector"] == "cleaning" and "Group 1" in s["category"] and s["job_level"] == level
            )
            source = get_schedule(schedule["id"])
            role.pwm = PWMConfig(
                schedule_id=source["id"],
                schedule_digest=source["digest"],
                covered_quantity=proposed,
                starting_salary=2300 if rid == "clean" else 4000,
                salary_source="Invented example salary-component schedule XT-EX1; not an actual employee salary record",
                applicability_confirmed=True,
                applicability_basis="Example assumes local full-time outsourced indoor office/commercial workers in this selected category; eligibility must be checked for operational use",
                remainder_flat_confirmed=True,
                oncost_rate=0.0,
                rationale="Example uses published schedule movements on the supplied salary component; remaining inclusive charges stay flat",
                beyond_published="hold last salary",
                beyond_reason="Explicit example assumption: hold the last projected salary after the published period; later policy changes are unknown and require officer review",
            )
            role.escalation = [0] * 6
            role.escalation_reason = "Example salary-only PWM projection; no overlapping general increase. Unpublished periods explicitly hold the last projected salary."
        plan.roles.append(role)
    for role in plan.roles:
        for kind, explanation in [
            ("quantity", role.quantity_reason),
            ("rate", role.rate_reason),
            ("escalation", role.escalation_reason),
        ]:
            record_basis(
                plan,
                kind,
                [role.id],
                "Illustrative example assumption",
                explanation,
                "Example setup XT-EX1; not independent market evidence",
                "officer assumption",
                actor,
            )
    for gate in ("profile", "responsibilities", "quantities", "plan", "rates", "base", "escalation"):
        confirm(plan, gate, actor, records)
    plan.ui_step = 5  # Final budget screen; legacy sixth wire location.
    plan.basis_drafts["example_project"] = True
    plan.history.append(
        {
            "action": "Prepared fictional Site Xtown example for final budget review; final approval remains outstanding",
            "version": plan.version,
            "officer": actor,
        }
    )
    return plan
