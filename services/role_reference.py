"""Reviewed title context only. No prices, workbook counts, equivalence or benchmark eligibility."""

import json
from pathlib import Path

ROLE_FAMILIES = {
    "Facilities management": [
        "Facilities Manager",
        "Senior Facilities Manager",
        "Assistant Facilities Manager",
    ],
    "Property management": [
        "Property Executive",
        "Senior Property Executive",
        "Property Officer",
        "Building Executive",
    ],
    "Technical": [
        "Technician",
        "Senior Technician",
        "Mobile Technician",
        "Shift Technician",
        "Technical Officer",
        "Audio-Visual Technician",
    ],
    "Administration": [
        "Administrative Assistant",
        "Admin Executive",
        "Admin Coordinator",
        "Admin/Helpdesk Officer",
        "Receptionist",
    ],
    "Engineering and specialists": [
        "M&E Engineer",
        "Assistant Engineer",
        "Licensed Electrical Worker",
        "Professional Engineer",
        "BMS/BOS Officer",
        "Fire Safety Manager",
        "Workplace Safety & Health Officer",
        "SCEM/Green Mark Manager",
    ],
    "Events and customer support": [
        "Program / Event Manager",
        "Event Coordinator",
        "Customer Service Officer",
        "Customer Service Executive",
        "Tenant Engagement Officer",
        "Digital Services Officer",
    ],
    "Combined duties": [
        "Property Executive cum FSM",
        "Senior Property Executive Cum FSM",
        "Administrative Assistant (cum Helpdesk and Event Support)",
    ],
    "Optional cleaning/security personnel": [
        "Cleaner",
        "Cleaning Floater",
        "Cleaning Supervisor",
        "Security Officer",
        "Senior Security Officer",
        "Security Supervisor",
    ],
}


def reference_context():
    return {
        "source": "Reviewed BCT manpower role inventory, 5 October 2026 (Markdown only)",
        "purpose": "Role-title context only; not cleaned/approved benchmark evidence",
        "families": ROLE_FAMILIES,
        "limitations": "Examples are not a closed list or equivalence mappings. Preserve exact title, seniority, combined duties and shared/fractional deployment. No BCT rates or statistical sample counts loaded. Cleaning/security personnel rates differ from total service charges.",
    }


def role_titles():
    catalog = json.loads(
        (Path(__file__).resolve().parents[1] / "data/reference/role_titles.json").read_text(encoding="utf-8")
    )
    examples = [r for family in ROLE_FAMILIES.values() for r in family]
    return sorted(set(examples + catalog["titles"]), key=str.casefold)
