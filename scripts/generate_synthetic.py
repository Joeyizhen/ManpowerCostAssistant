"""Reproducible fixture generation. Invented documents and values, explicitly labelled."""

import json
from pathlib import Path

from services.evidence import ROLES


def generate():
    rates = [7800, 6100, 4200, 3300, 3800, 5900, 3100, 6200]
    records = []
    for tender in range(10):
        for ri, role in enumerate(ROLES):
            for status in ["submitted", "awarded"]:
                sid = f"SYN-T{tender + 1:02d}-R{ri + 1:02d}-{status}"
                base = rates[ri] * (0.9 + tender * 0.025) * (1.025 if status == "submitted" else 1)
                growth = 0.015 + (tender % 5) * 0.005 + (ri % 3) * 0.002
                for year in range(1, 8):
                    records.append(
                        {
                            "record_id": f"{sid}-Y{year}",
                            "schedule_id": sid,
                            "tender_id": f"SYN-T{tender + 1:02d}",
                            "submission_year": 2023,
                            "contract_start_year": 2024,
                            "contract_duration": 7,
                            "contract_year": year,
                            "pricing_year": 2023 + year,
                            "raw_role_name": role,
                            "standard_role": role,
                            "quantity": 5 if role == "Technician" else (1 + tender % 2),
                            "unit_rate_monthly": round(base * (1 + growth) ** (year - 1), 2),
                            "currency": "SGD",
                            "rate_basis": "inclusive monthly per head",
                            "scope": "Public venue FM" if tender < 7 else "Office FM",
                            "inclusions": "Inclusive manpower quote; component split unavailable",
                            "exclusions": "Non-manpower supplies, specialist contracts, GST",
                            "award_status": status,
                            "validation_status": "validated",
                            "data_origin": "synthetic",
                            "source": f"Synthetic tender {tender + 1:02d}, invented pricing schedule",
                            "experience": None,
                            "qualifications": None,
                        }
                    )
    path = Path("data/sample")
    path.mkdir(parents=True, exist_ok=True)
    (path / "historical.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (path / "README.md").write_text(
        "# Synthetic fixtures\n\nAll records and document names are invented. Ten tenders, eight roles, submitted and awarded schedules, "
        "2024–2030 inclusive (seven years). No policy evidence or experience metadata is claimed. "
        "The 2023 submissions deliberately include future quotes. Regenerate with `uv run python -m scripts.generate_synthetic`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    generate()
