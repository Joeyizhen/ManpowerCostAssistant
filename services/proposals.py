"""Independent Track 2 proposal review. Private proposals never become reference data."""

import base64
import csv
import hashlib
import io
import json
import re
import zipfile
from uuid import uuid4
from xml.etree import ElementTree as ET

from pydantic import Field
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, select, update
from sqlalchemy.exc import IntegrityError

from services.calculations import budget, cents
from services.decision_basis import basis_errors, meaningful, record_basis, retained_basis
from services.evidence import map_role, rate_benchmark
from services.models import GATES, Finding, Plan, Profile, Role, StrictModel, now
from services.storage import ConflictError
from services.workflow import apply_change, confirm, findings, invalidate, requires_decision


class Proposal(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled proposal review"
    stage: int = Field(default=0, ge=0, le=2)
    plan: Plan = Field(default_factory=Plan)
    original: Plan | None = None
    original_digest: str = ""
    original_rows: list[dict] = Field(default_factory=list)
    documents: list[dict] = Field(default_factory=list)
    original_documents: list[dict] = Field(default_factory=list)
    original_text: str = ""
    input_text: str = ""
    input_rows: list[dict] = Field(default_factory=list)
    input_profile: dict = Field(default_factory=dict)
    drafts: dict = Field(default_factory=dict)
    claimed_total: float | None = Field(default=None, ge=0)
    original_claimed_total: float | None = Field(default=None, ge=0)
    interpretation_confirmed: bool = False
    history: list[dict] = Field(default_factory=list)
    quote_records: list[dict] = Field(default_factory=list)
    original_quote_records: list[dict] = Field(default_factory=list)


def original_signature(p):
    return hashlib.sha256(
        json.dumps(
            {
                "plan": p.original.model_dump(mode="json") if p.original else None,
                "rows": p.original_rows,
                "documents": p.original_documents,
                "text": p.original_text,
                "claimed": p.original_claimed_total,
                "quoted_prices": p.original_quote_records,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def restore_copy(source):
    """Restore a separate working review; source bytes/figures stay immutable."""
    if source.original and original_signature(source) != source.original_digest:
        raise ValueError("Original snapshot evidence digest does not match")
    restored = source.model_copy(deep=True)
    old_id, old_plan = restored.id, restored.plan.id
    restored.id, restored.plan.id = str(uuid4()), str(uuid4())

    def keys(value):
        if isinstance(value, dict):
            return {
                key.replace(old_id, restored.id).replace(old_plan, restored.plan.id): keys(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [keys(item) for item in value]
        return value

    restored.drafts = keys(restored.drafts)
    restored.plan.basis_drafts = keys(restored.plan.basis_drafts)
    prefix, new_prefix = f"private-proposal-{old_plan}-", f"private-proposal-{restored.plan.id}-"
    for role in restored.plan.roles:
        if role.schedule_id and role.schedule_id.startswith(prefix):
            role.schedule_id = role.schedule_id.replace(prefix, new_prefix, 1)
    for record in restored.quote_records:
        for field in ("record_id", "schedule_id"):
            record[field] = record[field].replace(prefix, new_prefix, 1)
        record["tender_id"] = restored.plan.id
    restored.plan.confirmations = {}
    restored.plan.final_officer = ""
    restored.plan.final_date = ""
    restored.plan.history.append(
        {
            "time": now(),
            "version": restored.plan.version,
            "action": "Restored separate proposal review; confirmation remains an officer action",
            "officer": "Snapshot restore",
        }
    )
    restored.stage = 1 if restored.original else 0
    return restored


class ProposalStore:
    """Separate owned tables and optimistic revisions; original evidence is immutable."""

    def __init__(self, engine):
        self.engine = engine
        meta = MetaData()
        columns = [
            Column("id", String(80), primary_key=True),
            Column("owner", String(128), nullable=False),
            Column("revision", Integer, nullable=False),
            Column("name", String(300)),
            Column("body", Text),
        ]
        self.projects = Table("proposal_reviews", meta, *columns)
        self.snapshots = Table(
            "proposal_review_snapshots",
            meta,
            Column("id", String(80), primary_key=True),
            Column("revision", Integer, primary_key=True),
            Column("owner", String(128), nullable=False),
            Column("body", Text),
        )
        meta.create_all(engine)

    def list(self, owner):
        with self.engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(self.projects.c.id, self.projects.c.name, self.projects.c.revision).where(
                        self.projects.c.owner == owner
                    )
                ).mappings()
            ]

    def load(self, pid, owner):
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(self.projects).where(self.projects.c.id == pid, self.projects.c.owner == owner)
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ValueError("Proposal not found or access denied")
        return Proposal.model_validate_json(row["body"]), row["revision"]

    def save(self, p, owner, expected):
        if p.original and original_signature(p) != p.original_digest:
            raise ValueError(
                "The original proposal cannot be overwritten. Start a separate review for a new original."
            )
        revision = expected + 1
        body = p.model_dump_json()
        try:
            with self.engine.begin() as conn:
                if expected:
                    old = conn.execute(
                        select(self.projects.c.body).where(
                            self.projects.c.id == p.id,
                            self.projects.c.owner == owner,
                            self.projects.c.revision == expected,
                        )
                    ).scalar_one_or_none()
                    if old is None:
                        raise ConflictError(
                            "A newer proposal revision exists. Download your snapshot and resume the latest revision."
                        )
                    prior = Proposal.model_validate_json(old)
                    if prior.original_digest and prior.original_digest != p.original_digest:
                        raise ValueError("Saved original proposal evidence is immutable")
                    conn.execute(
                        update(self.projects)
                        .where(
                            self.projects.c.id == p.id,
                            self.projects.c.owner == owner,
                            self.projects.c.revision == expected,
                        )
                        .values(revision=revision, name=p.name, body=body)
                    )
                else:
                    conn.execute(
                        self.projects.insert().values(
                            id=p.id, owner=owner, revision=revision, name=p.name, body=body
                        )
                    )
                conn.execute(
                    self.snapshots.insert().values(id=p.id, revision=revision, owner=owner, body=body)
                )
        except IntegrityError:
            raise ConflictError("Proposal already exists; resume its latest revision") from None
        return revision


ALIASES = {
    "role": "Role",
    "role title": "Role",
    "position": "Role",
    "designation": "Role",
    "quantity": "Quantity",
    "qty": "Quantity",
    "headcount": "Quantity",
    "fte": "Quantity",
    "unit": "Unit",
    "quantity basis": "Unit",
    "monthly rate": "Monthly rate",
    "rate": "Monthly rate",
    "unit rate": "Monthly rate",
    "monthly rate per head": "Monthly rate",
    "annual increase (%)": "Annual increase (%)",
    "escalation (%)": "Annual increase (%)",
    "escalation": "Annual increase (%)",
    "annual increase": "Annual increase (%)",
    "remarks": "Remarks",
    "duties": "Remarks",
    "notes": "Remarks",
    "experience": "Experience",
    "qualification": "Qualifications",
    "qualifications": "Qualifications",
    "mapping": "Mapping",
    "monthly total": "Supplied monthly total",
    "annual total": "Supplied annual total",
    "contract total": "Supplied contract total",
    "source location": "Source location",
    "pricing basis": "Pricing basis",
    "pricing reason": "Pricing basis",
}
COLUMNS = [
    "Role",
    "Quantity",
    "Unit",
    "Monthly rate",
    "Pricing basis",
    "Annual increase (%)",
    "Remarks",
    "Experience",
    "Qualifications",
    "Mapping",
    "Source location",
    "Supplied monthly total",
    "Supplied annual total",
    "Supplied contract total",
]


def number(value):
    if value is None or str(value).strip() in ("", "None", "nan"):
        return None
    text = str(value).strip().replace(",", "").replace("SGD", "").replace("$", "").rstrip("%")
    result = float(text)
    if not __import__("math").isfinite(result):
        raise ValueError("Numeric values must be finite")
    return result


def normalise_table(rows, source):
    result = []
    for index, raw in enumerate(rows, 2):
        row = {COLUMNS[i]: None for i in range(len(COLUMNS))}
        for key, value in raw.items():
            label = ALIASES.get(str(key).strip().casefold())
            if label:
                row[label] = value
        if not row["Role"]:
            continue
        row["Role"] = str(row["Role"]).strip()
        for label in (
            "Quantity",
            "Monthly rate",
            "Annual increase (%)",
            "Supplied monthly total",
            "Supplied annual total",
            "Supplied contract total",
        ):
            try:
                row[label] = number(row[label])
            except (ValueError, TypeError):
                row[label] = None  # Uninterpreted source remains in raw evidence; never a false zero.
        row["Unit"] = {"fte": "FTE", "headcount": "headcount", "heads": "headcount", "pax": "headcount"}.get(
            str(row["Unit"]).casefold(), "unspecified"
        )
        if row["Unit"] == "unspecified":
            headers = {str(k).strip().casefold() for k in raw}
            if "fte" in headers:
                row["Unit"] = "FTE"
            elif "headcount" in headers:
                row["Unit"] = "headcount"
        years = {}
        for key, value in raw.items():
            match = re.fullmatch(r"year\s*(\d+)\s*(?:monthly\s*)?(?:unit\s*)?rate", str(key).strip(), re.I)
            if match:
                if not 1 <= int(match[1]) <= 20:
                    raise ValueError("Quoted contract years must be within 1 to 20")
                years[int(match[1])] = number(value)
        if years:
            row["Yearly rates"] = [years.get(i) for i in range(1, max(years) + 1)]
            row["Monthly rate"] = row["Monthly rate"] or years.get(1)
        row["Source location"] = row["Source location"] or f"{source}, row {index}"
        row["raw"] = {str(k): str(v) if v is not None else "" for k, v in raw.items()}
        row["id"] = str(uuid4())
        result.append(row)
    return result


def interpret_text(text, source="Pasted text"):
    """Conservative table/free-text extraction. Officer confirms all interpretations."""
    if "\t" in text or ("," in text.splitlines()[0] if text.splitlines() else False):
        delimiter = "\t" if "\t" in text else ","
        parsed = normalise_table(list(csv.DictReader(io.StringIO(text), delimiter=delimiter)), source)
        if parsed:
            return parsed, []
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    pattern = (
        r"\b(\d+(?:\.\d+)?|"
        + "|".join(words)
        + r")\s+((?:(?:senior|junior|assistant|M&E|BMS)\s+)*(?:FM|facilit(?:y|ies)\s+managers?|engineers?|technicians?|administrators?|admin\s+executives?|cleaners?|security\s+officers?|landscape\s+workers?|lift\s+technicians?))\b"
    )
    extracted = []
    matches = list(re.finditer(pattern, text, re.I))
    for index, match in enumerate(matches):
        value, title = match.groups()
        source_end = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        tail = re.split(r"[,;\n.]", text[match.end() : end], maxsplit=1)[0].strip()
        if re.match(r"^(?:/|&|and\b|cum\b)\s*[^\d\s]", tail, re.I) and len(title + " " + tail) <= 160:
            title = title + " " + tail
            source_end = match.end() + len(re.split(r"[,;\n.]", text[match.end() : end], maxsplit=1)[0])
        qty = words[value.casefold()] if value.casefold() in words else float(value)
        extracted.append(
            {
                "Role": title,
                "Quantity": qty,
                "Source location": f"{source}, characters {match.start()}-{source_end}",
            }
        )
    rows = normalise_table(extracted, source)
    increase = re.search(
        r"([-+]?\d+(?:\.\d+)?)\s*%\s*(?:annual\s*)?(?:escalation|annual increase)", text, re.I
    )
    if increase:
        for row in rows:
            row["Annual increase (%)"] = float(increase[1])
    # No rate, unit, seniority or staffing rule is inferred from prose.
    note = [
        "Confirm the interpreted titles and quantities. Units, inclusive rates and yearly increases remain unanswered unless supplied in a labelled table."
    ]
    if not rows:
        note = [
            "No reliable role rows were identified. Keep the source and enter or correct the proposal table; no figures have been invented."
        ]
    return rows, note


def extract_document(name, data):
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Each proposal document must be 10 MB or smaller")
    suffix = name.rsplit(".", 1)[-1].casefold()
    rows, notes, text = [], [], ""
    if suffix in ("csv", "txt"):
        text = data.decode("utf-8-sig")
        rows, notes = interpret_text(text, name)
    elif suffix in ("xlsx", "docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("The expanded document is too large")
            if suffix == "docx":
                root = ET.fromstring(archive.read("word/document.xml"))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                text = "\n".join("".join(p.itertext()) for p in root.findall(".//w:p", ns))
                for index, table in enumerate(root.findall(".//w:tbl", ns), 1):
                    grid = [
                        ["".join(t.itertext()) for t in r.findall("w:tc", ns)]
                        for r in table.findall("w:tr", ns)
                    ]
                    if grid:
                        rows.extend(
                            normalise_table(
                                [dict(zip(grid[0], r, strict=False)) for r in grid[1:]],
                                f"{name}, table {index}",
                            )
                        )
            else:
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                strings = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                    strings = ["".join(x.itertext()) for x in root.findall("s:si", ns)]
                for sheet in sorted(
                    n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)
                ):
                    grid = []
                    for r in ET.fromstring(archive.read(sheet)).findall(".//s:row", ns):
                        values = {}
                        for cell in r.findall("s:c", ns):
                            v = cell.find("s:v", ns)
                            value = v.text if v is not None else "".join(cell.itertext())
                            if cell.get("t") == "s" and value:
                                value = strings[int(value)]
                            values[re.sub(r"\d", "", cell.get("r", ""))] = value
                        grid.append(values)
                    if grid:
                        headers = grid[0]
                        rows.extend(
                            normalise_table(
                                [{header: r.get(col) for col, header in headers.items()} for r in grid[1:]],
                                f"{name}, {sheet}",
                            )
                        )
                notes.append(
                    "Excel cached cell values were read; macros were not executed and formulas were not recalculated. Confirm the extracted figures."
                )
            if not rows:
                rows, more = interpret_text(text, name)
                notes.extend(more)
    elif suffix == "pdf":
        from pypdf import PdfReader

        for page, item in enumerate(PdfReader(io.BytesIO(data)).pages, 1):
            page_text = item.extract_text() or ""
            text += f"\nPage {page}\n{page_text}"
            found, _ = interpret_text(page_text, f"{name}, page {page}")
            rows.extend(found)
        notes.append(
            "PDF text extraction may not preserve table alignment. Confirm every extracted row; scanned pages need manual transcription or a text-readable source."
        )
    else:
        raise ValueError("Use CSV, XLSX, PDF, DOCX or text")
    return {
        "name": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes_base64": base64.b64encode(data).decode(),
        "text": text,
        "extraction_note": " ".join(notes),
        "rows": rows,
    }


def plan_from_rows(profile, rows, pid=None):
    plan = Plan(id=pid or str(uuid4()), profile=Profile.model_validate(profile))
    for index, row in enumerate(rows):
        if not str(row.get("Role") or "").strip():
            continue
        qty, rate, annual = (number(row.get(k)) for k in ("Quantity", "Monthly rate", "Annual increase (%)"))
        title = str(row["Role"]).strip()
        source = str(row.get("Source location") or f"Officer proposal, row {index + 1}")
        remarks = str(row.get("Remarks") or "")
        role = Role(
            id=str(row.get("id") or uuid4()),
            label=title,
            quantity=qty,
            included=qty != 0,
            exclusion_reason=remarks or "Zero quantity in supplied proposal" if qty == 0 else "",
            quantity_unit=str(row.get("Unit") or "unspecified"),
            mapped_role=row.get("Mapping") or map_role(title),
            duties_notes=remarks,
            experience=str(row.get("Experience") or ""),
            qualifications=str(row.get("Qualifications") or ""),
            rate=rate,
            rate_reason=str(row["Pricing basis"])
            if row.get("Pricing basis") is not None
            else f"Inclusive monthly manpower charge supplied at {source}; officer input, not independently verified.",
            escalation=[0.0]
            if plan.profile.years == 1
            else []
            if annual is None
            else [0.0] + [annual / 100] * max(0, plan.profile.years - 1),
            escalation_reason="Single-year contract; no future annual change."
            if plan.profile.years == 1
            else ""
            if annual is None
            else f"Supplied annual manpower increase of {annual:g}% from Year 2; {source}.",
            quantity_reason=remarks,
            benchmark_year=plan.profile.start_year
            or (plan.profile.start.year if plan.profile.start else None),
        )
        plan.roles.append(role)
    if not plan.roles:
        raise ValueError("Enter at least one proposed role")
    return plan


def capture_original(p, profile, rows, rate_basis_confirmed):
    if p.original:
        raise ValueError("Original already captured; use revisions rather than replacing the original")
    if not rate_basis_confirmed:
        raise ValueError(
            "Confirm whether the figures are inclusive monthly manpower charges; salaries cannot be silently treated as inclusive prices"
        )
    rows = [{**r, "id": str(r.get("id") or uuid4())} for r in rows]
    plan = plan_from_rows(profile, rows)
    quoted = []
    for role, row in zip(plan.roles, [r for r in rows if str(r.get("Role") or "").strip()], strict=True):
        if row.get("Yearly rates"):
            try:
                quoted.extend(
                    set_quote(
                        plan,
                        role.id,
                        row["Yearly rates"],
                        str(row.get("Source location") or "Supplied proposal"),
                    )
                )
            except ValueError as error:
                role.escalation = []
                role.escalation_reason = "Quoted prices need a reviewed interpretation before projection."
                p.drafts.setdefault("quote_interpretation_issues", []).append(str(error))
    p.original = plan.model_copy(deep=True)
    p.plan = plan
    p.name = plan.profile.name
    p.original_rows = json.loads(json.dumps(rows, default=str))
    p.original_documents = json.loads(json.dumps(p.documents))
    p.original_text = p.input_text
    p.original_claimed_total = p.claimed_total
    p.quote_records = quoted
    p.original_quote_records = list(quoted)
    p.original_digest = original_signature(p)
    p.interpretation_confirmed = True
    p.stage = 1
    p.history.append(
        {
            "time": now(),
            "action": "Officer confirmed proposal interpretation",
            "original_digest": p.original_digest,
        }
    )


def update_reviewed(p, profile, rows, officer):
    proposed = plan_from_rows(profile, rows, p.plan.id)
    candidate = p.plan.model_copy(deep=True)
    if proposed.profile != candidate.profile:
        apply_change(
            candidate,
            "profile",
            proposed.profile.model_dump(mode="json"),
            "Officer revised proposal context",
            officer,
        )
    original_ids = {r.id for r in candidate.roles}
    for role in proposed.roles:
        old = next((r for r in candidate.roles if r.id == role.id), None)
        if old:
            # Preserve advanced future profiles/PWM until an explicit future decision replaces them.
            old_annual = (
                old.escalation[1] * 100
                if len(old.escalation) > 1 and len(set(old.escalation[1:])) == 1
                else None
            )
            row = next(r for r in rows if str(r.get("id")) == role.id)
            original_source = next(
                (r.get("Source location") for r in p.original_rows if r["id"] == role.id), None
            )
            if (
                (role.rate != old.rate or role.quantity_unit != old.quantity_unit)
                and row.get("Source location") == original_source
                and row.get("Pricing basis") in (None, old.rate_reason)
            ):
                role.rate_reason = ""

            if number(row.get("Annual increase (%)")) == old_annual:
                for key in (
                    "escalation",
                    "escalation_mode",
                    "escalation_reason",
                    "schedule_id",
                    "pwm",
                    "policies",
                    "yearly_quantities",
                ):
                    setattr(role, key, getattr(old, key))
            for key in (
                "responsibility_ids",
                "mapping_reason",
                "rate_notes",
                "rate_origin",
                "benchmark_year",
                "benchmark_scope",
                "benchmark_status",
            ):
                setattr(role, key, getattr(old, key))
        if old != role:
            apply_change(
                candidate, "role", role.model_dump(mode="json"), "Officer revised proposed figures", officer
            )
        original_ids.discard(role.id)
    if original_ids:
        raise ValueError(
            "Use an explicit zero quantity and reason to exclude a role; do not delete its evidence row"
        )
    p.plan = candidate
    p.name = candidate.profile.name
    p.history.append(
        {"time": now(), "action": "Officer applied reviewed figures", "version": candidate.version}
    )


def assessment(p, records):
    records = records + p.quote_records
    plan = p.plan
    issues = findings(plan, records)
    extra = []
    for r in plan.roles:
        if r.included and r.quantity_unit not in ("headcount", "FTE"):
            extra.append(
                Finding(
                    id=f"proposal_unit:{r.id}",
                    code="proposal_unit",
                    role_id=r.id,
                    message=f"{r.label}: confirm headcount or FTE.",
                    impact="The proposal's unit must be explicit before costing.",
                    blocking=True,
                )
            )
    try:
        result = budget(plan, records) if not extra else None
    except ValueError:
        result = None
    if result:
        for row in p.original_rows:
            rid = row["id"]
            costs = [x for x in result["rows"] if x["role_id"] == rid]
            if not costs:
                continue
            values = {
                "Supplied monthly total": costs[0]["quantity"] * costs[0]["monthly_unit_rate"],
                "Supplied annual total": costs[0]["annual_cost"],
                "Supplied contract total": sum(x["annual_cost"] for x in costs),
            }
            for label, calculated in values.items():
                stated = number(row.get(label))
                if stated is not None and abs(stated - calculated) > 0.01:
                    fingerprint = hashlib.sha256(f"{rid}:{label}:{stated}:{calculated}".encode()).hexdigest()
                    f = Finding(
                        id=f"proposal_math:{rid}:{label}",
                        code="proposal_math",
                        role_id=rid,
                        message=f"{costs[0]['role']}: {label.lower()} {stated:,.2f}; reviewed calculation {calculated:,.2f}.",
                        impact="Keep the original figure in evidence and explicitly accept the corrected calculation or revise the inputs.",
                        fingerprint=fingerprint,
                    )
                    prior = plan.decisions.get(f.id)
                    extra.append(prior if prior and prior.fingerprint == fingerprint else f)
        if (
            p.original_claimed_total is not None
            and abs(p.original_claimed_total - result["contract_total"]) > 0.01
        ):
            fingerprint = hashlib.sha256(
                f"{p.original_claimed_total}:{result['contract_total']}".encode()
            ).hexdigest()
            f = Finding(
                id="proposal_total",
                code="proposal_math",
                message=f"Supplied EPV {p.original_claimed_total:,.2f}; reviewed EPV {result['contract_total']:,.2f}.",
                impact="The original claimed total is retained separately. Record why the reviewed total is accepted.",
                fingerprint=fingerprint,
            )
            old = plan.decisions.get(f.id)
            extra.append(old if old and old.fingerprint == fingerprint else f)
    labels = {}
    for role in plan.roles:
        labels.setdefault(role.label.casefold(), []).append(role.label)
    for key, values in labels.items():
        if len(values) > 1:
            f = Finding(
                id="proposal_duplicate:" + key,
                code="proposal_duplicate",
                message=f"{values[0]} appears in {len(values)} separate rows.",
                impact="Confirm these are separate positions rather than a duplicate cost line.",
                fingerprint=hashlib.sha256(
                    json.dumps(
                        [r.model_dump(mode="json") for r in plan.roles if r.label.casefold() == key],
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
            )
            old = plan.decisions.get(f.id)
            extra.append(old if old and old.fingerprint == f.fingerprint else f)
    unknown_capability = [
        r.label
        for r in plan.roles
        if r.included and (not r.experience.strip() or not r.qualifications.strip())
    ]
    if unknown_capability:
        extra.append(
            Finding(
                id="proposal_capability",
                code="proposal_capability",
                status="data limitation",
                message="Experience or qualification requirements are not separately confirmed for: "
                + "; ".join(dict.fromkeys(unknown_capability))
                + ".",
                impact="Seniority/capability fit is not established by rate comparisons alone; retain this qualification until supported.",
            )
        )
    for row in p.original_rows:
        if row.get("Yearly rates") and number(row.get("Annual increase (%)")) not in (None, 0):
            role = next((r for r in plan.roles if r.id == row["id"]), None)
            if role is None or not role.included:
                continue
            fingerprint = hashlib.sha256(
                json.dumps(
                    {"row": row, "mode": role.escalation_mode, "profile": role.escalation, "rate": role.rate},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            finding = Finding(
                id="proposal_quote_overlap:" + role.id,
                code="proposal_quote_overlap",
                role_id=role.id,
                message=role.label
                + ": the source supplies quoted yearly prices and a separate annual percentage.",
                impact="Full quoted prices receive no extra general increase. Confirm which source treatment is intended; never stack the same component twice.",
                fingerprint=fingerprint,
            )
            old = plan.decisions.get(finding.id)
            extra.append(old if old and old.fingerprint == fingerprint else finding)
    all_issues = issues + extra
    decisions = [
        f
        for f in all_issues
        if not f.blocking
        and requires_decision(f)
        and f.code != "proposal_capability"
        and (not f.officer or f.justification == "Officer justification was not provided.")
    ]
    return {
        "result": result,
        "findings": all_issues,
        "unresolved": decisions,
        "blockers": [f for f in all_issues if f.blocking],
        "basis_actions": list(
            dict.fromkeys(
                e for kind in ("rate", "escalation", "policy") for e in basis_errors(plan, kind, records)
            )
        ),
    }


def confirm_review(p, records, officer, deployment_note):
    if not p.interpretation_confirmed or not p.original:
        raise ValueError("Confirm the original proposal interpretation first")
    state = assessment(p, records)
    if state["blockers"] or state["unresolved"] or state["result"] is None:
        raise ValueError(
            "Resolve invalid inputs and material findings before confirming the reviewed proposal"
        )
    if not meaningful(deployment_note):
        raise ValueError(
            "Record the shared operational basis or a specific retained uncertainty for the proposed deployment"
        )
    if state["basis_actions"]:
        raise ValueError("\n".join(state["basis_actions"]))
    candidate = p.plan.model_copy(deep=True)
    for role in candidate.roles:
        if not retained_basis(candidate, role, "quantity"):
            record_basis(
                candidate,
                "quantity",
                [role.id],
                "Reviewed proposed deployment",
                deployment_note,
                "Officer-confirmed proposal review",
                "acknowledged uncertainty",
                officer,
            )
    # A single explicit review decision confirms these scopes; it does not approve the final EPV.
    for gate in GATES:
        confirm(candidate, gate, officer, records + p.quote_records)
    p.plan = candidate
    p.stage = 2
    p.drafts["deployment_note"] = deployment_note


def comparison(p, records):
    def calc(plan, quotes):
        try:
            if any(r.included and r.quantity_unit not in ("headcount", "FTE") for r in plan.roles):
                return None
            return budget(plan, records + quotes)
        except ValueError:
            return None

    original = calc(p.original, p.original_quote_records) if p.original else None
    reviewed = calc(p.plan, p.quote_records)
    old = original["contract_total"] if original else None
    new = reviewed["contract_total"] if reviewed else None
    delta = cents(new - old) if old is not None and new is not None else None
    return {
        "original": original,
        "reviewed": reviewed,
        "difference": delta,
        "percent": delta / old * 100 if delta is not None and old else None,
    }


def set_quote(plan, rid, prices, source):
    role = next(r for r in plan.roles if r.id == rid)
    if plan.profile.start is None or (plan.profile.start.month, plan.profile.start.day) != (1, 1):
        raise ValueError(
            "The existing calendar-year quote engine requires an actual 1 January start. Keep other actual dates and use an explicitly reviewed yearly assumption instead."
        )
    if not role.mapped_role:
        raise ValueError(
            f"{role.label}: quoted calendar prices need a confirmed supported mapping; do not infer a mapping from seniority or combined titles."
        )
    values = [number(x) for x in prices]
    if len(values) != plan.profile.years or any(x is None or x <= 0 for x in values):
        raise ValueError("Supply a positive quoted monthly rate for every contract year")
    if role.pwm or role.policies:
        raise ValueError("Review overlapping PWM/component treatment before selecting full quoted prices")
    sid = f"private-proposal-{plan.id}-{rid}"
    role.rate = values[0]
    role.escalation_mode, role.schedule_id = "quoted schedule", sid
    role.escalation = [0.0] * plan.profile.years
    role.escalation_reason = (
        "Year-specific inclusive prices supplied in the proposal; no additional general increase. " + source
    )
    return [
        {
            "record_id": f"{sid}-{i}",
            "schedule_id": sid,
            "tender_id": plan.id,
            "submission_year": plan.profile.start.year,
            "contract_start_year": plan.profile.start.year,
            "contract_duration": plan.profile.years,
            "contract_year": i + 1,
            "pricing_year": plan.profile.start.year + i,
            "raw_role_name": role.label,
            "standard_role": role.mapped_role,
            "quantity": role.quantity or 1,
            "unit_rate_monthly": value,
            "currency": "SGD",
            "rate_basis": "inclusive monthly per head",
            "scope": "Private proposal manpower charges",
            "award_status": "submitted",
            "validation_status": "proposal quotation",
            "data_origin": "private officer proposal",
            "source": source,
            "inclusions": "Officer-confirmed inclusive manpower charges",
            "exclusions": plan.profile.exclusions,
            "experience": role.experience,
            "qualifications": role.qualifications,
        }
        for i, value in enumerate(values)
    ]


def apply_yearly(p, rid, percentages, prices, source, officer):
    candidate = p.plan.model_copy(deep=True)
    role = next(r for r in candidate.roles if r.id == rid)
    if prices is not None:
        quotes = set_quote(candidate, rid, prices, source)
    else:
        values = [number(x) for x in percentages]
        if len(values) != candidate.profile.years or any(x is None for x in values) or values[0] != 0:
            raise ValueError("Enter every yearly increase, with 0 for Year 1")
        if role.pwm:
            raise ValueError("Remove or review PWM explicitly before replacing its salary treatment")
        role.escalation, role.escalation_mode, role.schedule_id = (
            [x / 100 for x in values],
            "assumption",
            None,
        )
        role.escalation_reason = source.strip() or "Officer-entered year-specific manpower cost assumptions"
        quotes = []
    invalidate(candidate, "escalation", "Officer revised proposal future prices", officer)
    p.plan = candidate
    p.quote_records = [
        r for r in p.quote_records if r["schedule_id"] != f"private-proposal-{candidate.id}-{rid}"
    ] + quotes


def rate_comparisons(plan, records):
    rows = []
    for r in plan.roles:
        if not r.included:
            continue
        bm = rate_benchmark(records, r.mapped_role, r.benchmark_year, r.benchmark_status, r.benchmark_scope)
        low, high = bm.get("minimum"), bm.get("maximum")
        rows.append(
            {
                "Role": r.label,
                "Proposed rate": r.rate,
                "Reference average": bm.get("average"),
                "Minimum": low,
                "Maximum": high,
                "Samples": bm["sample_count"],
                "Comparison": "No comparable range"
                if not bm["available"]
                else "Unanswered"
                if r.rate is None
                else "Below range"
                if r.rate < low
                else "Above range"
                if r.rate > high
                else "Within range",
            }
        )
    return rows
