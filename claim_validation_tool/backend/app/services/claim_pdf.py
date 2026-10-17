"""PDFs of a submitted claim, both built from the 837 saved at submission:

- claim_form_pdf: the claim laid out like the paper form billers know, CMS-1500 for 837P
  and UB-04 for 837I, with the official box numbers. A reference copy for reading and
  printing; payers that take paper scan the official red-ink form, not this.
- readable_837_pdf: the 837 broken into named sections, each value with where it sits in
  the file, and the raw file at the end.

A test file gets a "TEST FILE" mark on every page.
"""

from collections.abc import Callable, Mapping
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.edi_reader import FILING_CODES, RELATIONSHIPS, RESPONSIBILITY, Claim837, Party

INK = colors.HexColor("#1d1d1f")
MUTED = colors.HexColor("#6e6e76")
RULE = colors.HexColor("#d1d1d7")
FORM_RED = colors.HexColor("#b4232a")  # the forms' printed red, for box labels

LABEL = ParagraphStyle("label", fontName="Helvetica", fontSize=6, leading=7.5, textColor=FORM_RED)
VALUE = ParagraphStyle("value", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=INK)
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=MUTED)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK)
HEADING = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK, spaceBefore=10, spaceAfter=4)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)
SOURCE = ParagraphStyle("source", fontName="Courier", fontSize=7, leading=9, textColor=MUTED)
RAW = ParagraphStyle("raw", fontName="Courier", fontSize=7, leading=8.5, textColor=INK)

PAGE_WIDTH = LETTER[0] - inch  # inside half-inch margins

REVENUE_CODES = {
    "0250": "Pharmacy",
    "0300": "Laboratory",
    "0320": "Radiology, diagnostic",
    "0360": "Operating room",
    "0450": "Emergency room",
    "0510": "Clinic",
    "0636": "Drugs, detailed coding",
    "0730": "EKG/ECG",
    "0920": "Other diagnostic services",
}
SEXES = {"F": "Female", "M": "Male", "U": "Unknown"}


def _hex(color: colors.Color) -> str:
    """#rrggbb for reportlab's inline <font color> markup."""
    return "#" + color.hexval()[2:]


def _text(value: object) -> str:
    return escape(str(value)) if value not in (None, "") else "—"


def _box(label: str, *values: object) -> Paragraph:
    lines = "<br/>".join(_text(v) for v in values if v not in (None, "")) or "—"
    return Paragraph(f'<font size="6" color="{_hex(FORM_RED)}">{escape(label)}</font><br/>{lines}', VALUE)


def _address(party: Party) -> list[str]:
    return [*party.address, party.city_line]


def _grid(rows: list[list], widths: list[float], spans: list[tuple] = ()) -> Table:
    table = Table(rows, colWidths=[w * PAGE_WIDTH for w in widths])
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, FORM_RED),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    style += [("SPAN", start, end) for start, end in spans]
    table.setStyle(TableStyle(style))
    return table


def _page_decorations(claim: Claim837, footer: str) -> Callable:
    def draw(canvas, doc) -> None:
        canvas.saveState()
        if claim.test:
            canvas.setFillColor(colors.Color(0.85, 0.45, 0.1, alpha=0.12))
            canvas.setFont("Helvetica-Bold", 54)
            canvas.translate(LETTER[0] / 2, LETTER[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "TEST FILE")
            canvas.rotate(-35)
            canvas.translate(-LETTER[0] / 2, -LETTER[1] / 2)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.5 * inch, 0.35 * inch, footer)
        canvas.drawRightString(LETTER[0] - 0.5 * inch, 0.35 * inch, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _build(story: list, claim: Claim837, title: str, footer: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER, leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch, bottomMargin=0.6 * inch, title=title,
        author="ClaustraRCM", subject=f"Claim {claim.claim_id}",
    )
    decorate = _page_decorations(claim, footer)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def _footer(claim: Claim837) -> str:
    usage = "TEST FILE — not sent to a payer" if claim.test else "Production file"
    return f"{claim.claim_id} · built from the {claim.transaction} saved at submission ({claim.created}) · control number {claim.control_number} · {usage}"


def _header(claim: Claim837, form_name: str, note: str) -> Table:
    payer = claim.policy.payer
    left = Paragraph(f"{form_name}<br/><font size='7.5' color='{_hex(MUTED)}'>{escape(note)}</font>", TITLE)
    right = _box("CARRIER / PAYER", payer.name, f"Payer ID {payer.id}")
    table = Table([[left, right]], colWidths=[0.62 * PAGE_WIDTH, 0.38 * PAGE_WIDTH])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    return table


# --- Claim form ---------------------------------------------------------------------


def claim_form_pdf(claim: Claim837, procedures: Mapping[str, str]) -> bytes:
    """CMS-1500 (837P) or UB-04 (837I) layout. `procedures` maps CPT code to description."""
    story = _ub04(claim, procedures) if claim.institutional else _cms1500(claim, procedures)
    name = "UB-04" if claim.institutional else "CMS-1500"
    return _build(story, claim, f"{name} claim form — {claim.claim_id}", _footer(claim))


def _cms1500(claim: Claim837, procedures: Mapping[str, str]) -> list:
    patient = claim.patient_party
    insured = claim.policy.holder
    other = claim.other_policies[0] if claim.other_policies else None
    letters = "ABCDEFGHIJKL"
    story = [
        _header(claim, "HEALTH INSURANCE CLAIM FORM", "CMS-1500 (02/12) layout · reference copy for reading and printing, not an OCR form"),
        Spacer(1, 8),
        _grid(
            [
                [_box("1. TYPE OF INSURANCE", FILING_CODES.get(claim.policy.filing_code, claim.policy.filing_code)), "", _box("1a. INSURED'S I.D. NUMBER", insured.id)],
                [_box("2. PATIENT'S NAME (Last, First)", patient.full_name), _box("3. PATIENT'S BIRTH DATE · SEX", patient.birth_date, SEXES.get(patient.sex, patient.sex)), _box("4. INSURED'S NAME (Last, First)", insured.full_name)],
                [_box("5. PATIENT'S ADDRESS", *_address(patient)), _box("6. PATIENT RELATIONSHIP TO INSURED", RELATIONSHIPS.get(claim.policy.relationship, claim.policy.relationship)), _box("7. INSURED'S ADDRESS", *(_address(insured) if insured.address else ["Same as patient"]))],
                [_box("9. OTHER INSURED'S NAME", other.holder.full_name if other else None), _box("10. IS PATIENT'S CONDITION RELATED TO", "Not reported"), _box("11. INSURED'S POLICY GROUP OR FECA NUMBER", claim.policy.group_number or "None")],
                [_box("9a. OTHER INSURED'S POLICY OR GROUP NUMBER", other.holder.id if other else None), _box("9d. OTHER INSURANCE PLAN NAME", other.payer.name if other else None), _box("11c. INSURANCE PLAN NAME · 11d. ANOTHER HEALTH BENEFIT PLAN?", claim.policy.payer.name, "Yes" if other else "No")],
                [_box("12. PATIENT'S OR AUTHORIZED PERSON'S SIGNATURE", "Signature on file"), "", _box("13. INSURED'S OR AUTHORIZED PERSON'S SIGNATURE", "Signature on file")],
            ],
            [0.36, 0.28, 0.36],
            spans=[((0, 0), (1, 0)), ((0, 5), (1, 5))],
        ),
        Spacer(1, 6),
        _grid(
            [
                [_box("21. DIAGNOSIS OR NATURE OF ILLNESS OR INJURY (ICD Ind. 0)", "   ".join(f"{letters[i]}. {code}" for i, code in enumerate(claim.diagnoses))), ""],
                [_box("22. RESUBMISSION CODE", "Original claim" if claim.frequency == "1" else claim.frequency), _box("23. PRIOR AUTHORIZATION NUMBER", claim.prior_auth or "None")],
            ],
            [0.5, 0.5],
            spans=[((0, 0), (1, 0))],
        ),
        Spacer(1, 6),
    ]
    head = ["24A. DATE(S) OF SERVICE", "B. POS", "D. PROCEDURES · MODIFIER", "E. DX POINTER", "F. CHARGES", "G. UNITS", "J. RENDERING NPI"]
    rows = [[Paragraph(escape(h), LABEL) for h in head]]
    for line in claim.lines:
        description = procedures.get(line.procedure, "")
        pointer = letters[int(line.pointer) - 1] if line.pointer.isdigit() else line.pointer
        rows.append([
            Paragraph(_text(line.service_date), CELL),
            Paragraph(_text(claim.place_or_bill), CELL),
            Paragraph(f"{_text(line.procedure)} {escape(' '.join(line.modifiers))}<br/><font size='6.5' color='{_hex(MUTED)}'>{escape(description)}</font>", CELL),
            Paragraph(_text(pointer), CELL),
            Paragraph(f"${float(line.charge):,.2f}", CELL),
            Paragraph(_text(line.units), CELL),
            Paragraph(_text(claim.provider.id), CELL),
        ])
    story.append(_grid(rows, [0.14, 0.07, 0.3, 0.1, 0.13, 0.08, 0.18]))
    story += [
        Spacer(1, 6),
        _grid(
            [
                [_box("25. FEDERAL TAX I.D. NUMBER (EIN)", claim.billing_tax_id), _box("26. PATIENT'S ACCOUNT NO.", claim.claim_id), _box("27. ACCEPT ASSIGNMENT?", "Yes"), _box("28. TOTAL CHARGE", f"${float(claim.total_charge):,.2f}"), _box("29. AMOUNT PAID", "$0.00")],
                [_box("31. SIGNATURE OF PHYSICIAN OR SUPPLIER", claim.provider.full_name, f"NPI {claim.provider.id}"), "", _box("32. SERVICE FACILITY LOCATION", claim.facility.name, *_address(claim.facility)), "", _box("33. BILLING PROVIDER INFO", claim.billing.name, *_address(claim.billing), f"33a. NPI {claim.billing.id}")],
            ],
            [0.22, 0.2, 0.16, 0.2, 0.22],
            spans=[((0, 1), (1, 1)), ((2, 1), (3, 1))],
        ),
    ]
    return story


def _ub04(claim: Claim837, procedures: Mapping[str, str]) -> list:
    patient = claim.patient_party
    insured = claim.policy.holder
    bill = f"0{claim.place_or_bill}{claim.frequency}"
    story = [
        _header(claim, "UB-04 CLAIM FORM", "UB-04 (CMS-1450) layout · reference copy for reading and printing, not an OCR form"),
        Spacer(1, 8),
        _grid(
            [
                [_box("1. BILLING PROVIDER", claim.billing.name, *_address(claim.billing)), _box("3a. PAT. CNTL #", claim.claim_id), _box("4. TYPE OF BILL", bill)],
                [_box("5. FED. TAX NO.", claim.billing_tax_id), _box("6. STATEMENT COVERS PERIOD", claim.statement_period), _box("56. NPI", claim.billing.id)],
                [_box("8. PATIENT NAME", patient.full_name), _box("9. PATIENT ADDRESS", *_address(patient)), _box("10. BIRTHDATE · 11. SEX", patient.birth_date, SEXES.get(patient.sex, patient.sex))],
                [_box("14. ADMISSION TYPE", claim.admission_type), _box("15. POINT OF ORIGIN", claim.admission_source), _box("17. PATIENT STATUS", claim.patient_status)],
            ],
            [0.4, 0.35, 0.25],
        ),
        Spacer(1, 6),
    ]
    head = ["42. REV. CD.", "43. DESCRIPTION", "44. HCPCS / RATES", "45. SERV. DATE", "46. SERV. UNITS", "47. TOTAL CHARGES", "48. NON-COVERED"]
    rows = [[Paragraph(escape(h), LABEL) for h in head]]
    for line in claim.lines:
        description = REVENUE_CODES.get(line.revenue_code) or procedures.get(line.procedure, "")
        rows.append([
            Paragraph(_text(line.revenue_code), CELL),
            Paragraph(_text(description), CELL),
            Paragraph(f"{_text(line.procedure)} {escape(' '.join(line.modifiers))}", CELL),
            Paragraph(_text(line.service_date), CELL),
            Paragraph(_text(line.units), CELL),
            Paragraph(f"${float(line.charge):,.2f}", CELL),
            Paragraph("$0.00", CELL),
        ])
    rows.append([Paragraph("0001", CELL), Paragraph("TOTALS", CELL), "", "", "", Paragraph(f"${float(claim.total_charge):,.2f}", CELL), Paragraph("$0.00", CELL)])
    story.append(_grid(rows, [0.1, 0.24, 0.16, 0.13, 0.11, 0.14, 0.12]))
    payers = [claim.policy, *claim.other_policies]
    story += [
        Spacer(1, 6),
        _grid(
            [[Paragraph(escape(h), LABEL) for h in ["", "50. PAYER NAME", "51. HEALTH PLAN ID", "52. REL. INFO", "53. ASG. BEN.", "58. INSURED'S NAME", "59. P. REL", "60. INSURED'S UNIQUE ID", "62. GROUP NO."]]]
            + [
                [
                    Paragraph("ABC"[index], CELL),
                    Paragraph(_text(policy.payer.name), CELL),
                    Paragraph(_text(policy.payer.id), CELL),
                    Paragraph("Y", CELL),
                    Paragraph("Y", CELL),
                    Paragraph(_text((policy.holder.full_name if policy.holder.name else patient.full_name)), CELL),
                    Paragraph(_text(f"{policy.relationship} · {RELATIONSHIPS.get(policy.relationship, '')}"), CELL),
                    Paragraph(_text(policy.holder.id), CELL),
                    Paragraph(_text(policy.group_number), CELL),
                ]
                for index, policy in enumerate(payers)
            ],
            [0.04, 0.16, 0.11, 0.07, 0.07, 0.17, 0.07, 0.18, 0.13],
        ),
        Spacer(1, 6),
        _grid(
            [
                [_box("63. TREATMENT AUTHORIZATION CODES", claim.prior_auth or "None"), _box("66. DX · 67. PRINCIPAL DIAGNOSIS CODE", "0 (ICD-10)", claim.diagnoses[0] if claim.diagnoses else None), _box("67A–Q. OTHER DIAGNOSIS CODES", "  ".join(claim.diagnoses[1:]) or "None")],
                [_box("76. ATTENDING", claim.provider.full_name, f"NPI {claim.provider.id}"), _box("SERVICE FACILITY", claim.facility.name, *_address(claim.facility)), _box("INSURED'S ADDRESS", *(_address(insured) if insured.address else ["Same as patient"]))],
            ],
            [0.34, 0.33, 0.33],
        ),
    ]
    return story


# --- Readable 837 ---------------------------------------------------------------------


def _section(title: str, rows: list[tuple[str, object, str]]) -> KeepTogether:
    data = [[Paragraph(escape(label), CELL), Paragraph(_text(value), CELL), Paragraph(escape(source), SOURCE)] for label, value, source in rows]
    table = Table(data, colWidths=[0.3 * PAGE_WIDTH, 0.45 * PAGE_WIDTH, 0.25 * PAGE_WIDTH])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return KeepTogether([Paragraph(escape(title), HEADING), table])


def _party_rows(party: Party, prefix: str, id_label: str = "ID") -> list[tuple[str, object, str]]:
    rows = [("Name", party.full_name, f"{prefix} · NM103–NM104"), (id_label, party.id, f"{prefix} · NM109")]
    if party.address:
        rows += [("Address", ", ".join(_address(party)), "N3 · N4")]
    if party.birth_date:
        rows += [("Date of birth", party.birth_date, "DMG02"), ("Sex", SEXES.get(party.sex, party.sex), "DMG03")]
    return rows


def readable_837_pdf(claim: Claim837) -> bytes:
    usage = "Test file (ISA15 = T)" if claim.test else "Production (ISA15 = P)"
    story = [
        Paragraph(f"{claim.transaction} claim file — readable copy", TITLE),
        Paragraph(escape(f"Claim {claim.claim_id} · {usage} · each value with where it sits in the file"), SMALL),
        _section("Interchange", [
            ("Sender (submitter) ID", claim.sender_id, "ISA06"),
            ("Receiver (clearinghouse) ID", claim.receiver_id, "ISA08"),
            ("Created", claim.created, "ISA09–ISA10"),
            ("Control number", claim.control_number, "ISA13 · IEA02"),
            ("Usage", usage, "ISA15"),
            ("Implementation guide", claim.version, "GS08 · ST03"),
        ]),
        _section("Submitter (1000A)", [
            *_party_rows(claim.submitter, "NM1*41"),
            ("Contact", claim.submitter_contact, "PER02"),
            ("Phone", claim.submitter_phone, "PER04"),
        ]),
        _section("Receiver (1000B)", _party_rows(claim.receiver, "NM1*40")),
        _section("Billing provider (2010AA)", [
            *_party_rows(claim.billing, "NM1*85", "NPI"),
            ("Tax ID (EIN)", claim.billing_tax_id, "REF*EI"),
        ]),
        _section("Subscriber (2000B · 2010BA)", [
            ("Payer responsibility", RESPONSIBILITY.get(claim.policy.responsibility, claim.policy.responsibility), "SBR01"),
            ("Relationship to patient", RELATIONSHIPS.get(claim.policy.relationship, claim.policy.relationship), "SBR02 · PAT01"),
            ("Group number", claim.policy.group_number or "None", "SBR03"),
            ("Insurance type", f"{claim.policy.filing_code} · {FILING_CODES.get(claim.policy.filing_code, '')}", "SBR09"),
            *_party_rows(claim.policy.holder, "NM1*IL", "Member ID"),
        ]),
        _section("Payer (2010BB)", _party_rows(claim.policy.payer, "NM1*PR", "Payer ID")),
    ]
    if claim.patient:
        story.append(_section("Patient (2000C · 2010CA)", _party_rows(claim.patient, "NM1*QC")))
    claim_rows = [
        ("Claim ID (patient account)", claim.claim_id, "CLM01"),
        ("Total charge", f"${float(claim.total_charge):,.2f}", "CLM02"),
    ]
    if claim.institutional:
        claim_rows += [
            ("Type of bill", f"0{claim.place_or_bill}{claim.frequency}", "CLM05"),
            ("Statement period", claim.statement_period, "DTP*434"),
            ("Admission type · point of origin · status", f"{claim.admission_type} · {claim.admission_source} · {claim.patient_status}", "CL101–CL103"),
        ]
    else:
        claim_rows += [("Place of service · frequency", f"{claim.place_or_bill} · {claim.frequency}", "CLM05")]
    claim_rows += [
        ("Prior authorization", claim.prior_auth or "None", "REF*G1"),
        ("Diagnoses", ", ".join(claim.diagnoses), "HI (ABK principal, ABF others)"),
    ]
    story.append(_section("Claim (2300)", claim_rows))
    role = "Attending provider (2310A)" if claim.institutional else "Rendering provider (2310B)"
    story.append(_section(role, _party_rows(claim.provider, "NM1*71" if claim.institutional else "NM1*82", "NPI")))
    story.append(_section("Service facility", _party_rows(claim.facility, "NM1*77")))
    for policy in claim.other_policies:
        story.append(_section(f"Other coverage — {RESPONSIBILITY.get(policy.responsibility, policy.responsibility)} (2320 · 2330)", [
            ("Relationship to patient", RELATIONSHIPS.get(policy.relationship, policy.relationship), "SBR02"),
            ("Insurance type", f"{policy.filing_code} · {FILING_CODES.get(policy.filing_code, '')}", "SBR09"),
            *_party_rows(policy.holder, "NM1*IL", "Member ID"),
            ("Payer", policy.payer.name, "NM1*PR · NM103"),
            ("Payer ID", policy.payer.id, "NM1*PR · NM109"),
        ]))

    head = ["#", "Revenue" if claim.institutional else "Dx ptr", "Procedure", "Modifiers", "Units", "Charge", "Date"]
    rows = [[Paragraph(escape(h), SOURCE) for h in head]]
    for line in claim.lines:
        rows.append([Paragraph(_text(v), CELL) for v in (
            line.number,
            line.revenue_code if claim.institutional else line.pointer,
            line.procedure,
            " ".join(line.modifiers) or "—",
            line.units,
            f"${float(line.charge):,.2f}",
            line.service_date,
        )])
    lines_table = Table(rows, colWidths=[w * PAGE_WIDTH for w in (0.06, 0.12, 0.18, 0.14, 0.1, 0.18, 0.22)])
    lines_table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    source = "LX · SV2 · DTP*472" if claim.institutional else "LX · SV1 · DTP*472"
    story += [
        KeepTogether([Paragraph(f"Service lines (2400) <font name='Courier' size='7' color='{_hex(MUTED)}'>{source}</font>", HEADING), lines_table]),
        Paragraph("The file as sent", HEADING),
        Preformatted("\n".join(segment + "~" for segment in claim.segments), RAW, maxLineLength=110),
    ]
    return _build(story, claim, f"{claim.transaction} readable copy — {claim.claim_id}", _footer(claim))
