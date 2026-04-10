"""
Data export router — download raw or processed data as Excel (.xlsx), JSON, CSV, or PDF.
"""
import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AgentRunDB, OffsetPurchaseDB, ScenarioDB, UserDB, get_db
from app.models.schemas import (
    OffsetPortfolioSummary,
    ScenarioComplianceOverrides,
    ScenarioReportMetric,
    ScenarioReportPayload,
)
from app.routers.auth import get_current_user
from app.services.emissions_engine import get_benchmark_comparison
from app.services.financial_engine import get_compliance_report

router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"
_REPORT_METHODODOLOGY = "GHG Protocol Corporate Standard, ISO 14064-1"
_REPORT_DISCLAIMER = (
    "Calculations are based on industry-standard emission factors and scenario assumptions. "
    "Actual emissions may vary. For verified reporting, engage an accredited third-party verifier."
)
_CATEGORY_LABELS = [
    ("travel_tco2e", "Travel"),
    ("venue_energy_tco2e", "Venue Energy"),
    ("accommodation_tco2e", "Accommodation"),
    ("catering_tco2e", "Catering"),
    ("materials_waste_tco2e", "Materials & Waste"),
    ("equipment_tco2e", "Equipment"),
    ("swag_tco2e", "Swag"),
]


def _wb_response(wb, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _style_header(ws, row=1):
    """Bold + green background for header row."""
    from openpyxl.styles import Alignment, Font, PatternFill

    fill = PatternFill("solid", fgColor="1A9E6E")
    for cell in ws[row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")


def _iso(dt: Optional[datetime]) -> str:
    return dt.isoformat() if dt else ""


def _labelize(value: str) -> str:
    return value.replace("_", " ").replace("/", " / ").title()


def _scenario_location(s: ScenarioDB) -> str:
    return getattr(s, "location", None) or (s.input_payload or {}).get("location", "")


def _serialize_scenario_row(s: ScenarioDB) -> dict[str, Any]:
    event_type = getattr(s, "event_type", "conference") or "conference"
    per_attendee_day = round(s.per_attendee_tco2e / max(s.event_days or 1, 1), 4) if s.per_attendee_tco2e else 0
    benchmark = get_benchmark_comparison(event_type, per_attendee_day)
    return {
        "scenario_id": s.id,
        "name": s.name,
        "event_name": s.event_name,
        "location": _scenario_location(s),
        "event_type": event_type,
        "attendees": s.attendees,
        "event_days": s.event_days,
        "mode": s.mode,
        "emissions": {
            "travel_tco2e": s.travel_tco2e,
            "venue_energy_tco2e": s.venue_energy_tco2e,
            "accommodation_tco2e": s.accommodation_tco2e,
            "catering_tco2e": s.catering_tco2e,
            "materials_waste_tco2e": s.materials_waste_tco2e,
            "equipment_tco2e": getattr(s, "equipment_tco2e", 0) or 0,
            "swag_tco2e": getattr(s, "swag_tco2e", 0) or 0,
            "total_tco2e": s.total_tco2e,
            "per_attendee_tco2e": s.per_attendee_tco2e,
            "per_attendee_day_tco2e": per_attendee_day,
            "data_quality": s.data_quality,
            "scopes": {
                "scope1_tco2e": getattr(s, "scope1_tco2e", 0) or 0,
                "scope2_tco2e": getattr(s, "scope2_tco2e", 0) or 0,
                "scope3_tco2e": getattr(s, "scope3_tco2e", 0) or 0,
            },
        },
        "assumptions": s.assumptions or {},
        "input_payload": s.input_payload or {},
        "factors_snapshot": getattr(s, "factors_snapshot", None) or {},
        "benchmark": benchmark.model_dump() if benchmark else None,
        "created_at": _iso(s.created_at),
    }


async def _get_scenario_or_404(
    scenario_id: str,
    db: AsyncSession,
    current_user: UserDB,
) -> ScenarioDB:
    scenario = await db.scalar(
        select(ScenarioDB).where(
            ScenarioDB.id == scenario_id,
            ScenarioDB.user_id == current_user.id,
        )
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


def _build_category_rows(scenario_data: dict[str, Any]) -> list[ScenarioReportMetric]:
    emissions = scenario_data["emissions"]
    total = emissions.get("total_tco2e") or 0
    rows: list[ScenarioReportMetric] = []
    for key, label in _CATEGORY_LABELS:
        value = float(emissions.get(key, 0) or 0)
        if value <= 0:
            continue
        pct_total = round((value / total) * 100, 1) if total > 0 else None
        rows.append(
            ScenarioReportMetric(
                key=key,
                label=label,
                value=round(value, 4),
                unit="tCO2e",
                pct_total=pct_total,
            )
        )
    return rows


async def _build_offset_summary_for_scenario(
    scenario_id: str,
    user_id: int,
    total_tco2e: float,
    db: AsyncSession,
) -> OffsetPortfolioSummary:
    result = await db.execute(
        select(OffsetPurchaseDB).where(
            OffsetPurchaseDB.user_id == user_id,
            OffsetPurchaseDB.scenario_id == scenario_id,
            OffsetPurchaseDB.status != "cancelled",
        )
    )
    purchases = result.scalars().all()

    total_purchased = sum(p.quantity_tco2e for p in purchases)
    total_retired = sum(p.quantity_tco2e for p in purchases if p.status == "retired")
    total_cost = sum(p.total_cost_usd for p in purchases)

    by_type: dict[str, float] = {}
    by_registry: dict[str, float] = {}
    for purchase in purchases:
        by_type[purchase.project_type] = by_type.get(purchase.project_type, 0) + purchase.quantity_tco2e
        by_registry[purchase.registry] = by_registry.get(purchase.registry, 0) + purchase.quantity_tco2e

    coverage_pct = None
    if total_tco2e > 0:
        coverage_pct = round(total_retired / total_tco2e * 100, 1)

    return OffsetPortfolioSummary(
        total_purchased_tco2e=round(total_purchased, 3),
        total_retired_tco2e=round(total_retired, 3),
        total_cost_usd=round(total_cost, 2),
        by_project_type=by_type,
        by_registry=by_registry,
        coverage_pct=coverage_pct,
    )


async def build_scenario_report_payload(
    scenario_id: str,
    db: AsyncSession,
    current_user: UserDB,
    region: str = "singapore",
    has_scope3: bool = True,
    has_ghg_report: bool = False,
) -> ScenarioReportPayload:
    scenario = await _get_scenario_or_404(scenario_id, db, current_user)
    scenario_data = _serialize_scenario_row(scenario)
    categories = _build_category_rows(scenario_data)
    emissions = scenario_data["emissions"]
    offset_summary = await _build_offset_summary_for_scenario(
        scenario_id=scenario.id,
        user_id=current_user.id,
        total_tco2e=float(emissions.get("total_tco2e") or 0),
        db=db,
    )
    compliance = get_compliance_report(
        total_tco2e=float(emissions.get("total_tco2e") or 0),
        has_scope3=has_scope3,
        has_ghg_report=has_ghg_report,
        region=region,
        event_days=int(scenario.event_days or 0),
        attendees=int(scenario.attendees or 0),
    )

    return ScenarioReportPayload(
        report_title=f"Carbon Footprint Report - {scenario.event_name or scenario.name}",
        exported_at=datetime.utcnow().isoformat(),
        methodology=_REPORT_METHODODOLOGY,
        disclaimer=_REPORT_DISCLAIMER,
        scenario=scenario_data,
        categories=categories,
        scope_breakdown=emissions["scopes"],
        benchmark=scenario_data.get("benchmark"),
        assumptions=scenario_data.get("assumptions", {}),
        factor_snapshot=scenario_data.get("factors_snapshot", {}),
        offset_portfolio=offset_summary,
        compliance=compliance,
        compliance_overrides=ScenarioComplianceOverrides(
            region=region,
            has_scope3=has_scope3,
            has_ghg_report=has_ghg_report,
        ),
    )


def _scenario_report_filename(prefix: str, scenario_id: str, extension: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return f"{prefix}_{scenario_id}_{stamp}.{extension}"


def _csv_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _pdf_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _scenario_report_csv_bytes(report: ScenarioReportPayload) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "label", "value", "unit"])

    scenario = report.scenario
    emissions = scenario["emissions"]
    metadata_rows = [
        ("metadata", "scenario_id", "Scenario ID", scenario["scenario_id"], ""),
        ("metadata", "name", "Scenario Name", scenario["name"], ""),
        ("metadata", "event_name", "Event Name", scenario["event_name"], ""),
        ("metadata", "location", "Location", scenario["location"], ""),
        ("metadata", "event_type", "Event Type", scenario["event_type"], ""),
        ("metadata", "attendees", "Attendees", scenario["attendees"], "count"),
        ("metadata", "event_days", "Event Days", scenario["event_days"], "days"),
        ("metadata", "mode", "Mode", scenario.get("mode", ""), ""),
        ("metadata", "data_quality", "Data Quality", emissions["data_quality"], ""),
        ("metadata", "created_at", "Created At", scenario["created_at"], ""),
        ("metadata", "exported_at", "Exported At", report.exported_at, ""),
        ("metadata", "region", "Compliance Region", report.compliance_overrides.region, ""),
        ("metadata", "has_scope3", "Has Scope 3", report.compliance_overrides.has_scope3, "boolean"),
        ("metadata", "has_ghg_report", "Has GHG Report", report.compliance_overrides.has_ghg_report, "boolean"),
    ]
    writer.writerows(metadata_rows)

    for category in report.categories:
        writer.writerow(("categories", category.key, category.label, category.value, category.unit))
        if category.pct_total is not None:
            writer.writerow(
                ("categories_pct", f"{category.key}_pct_total", f"{category.label} % of total", category.pct_total, "pct")
            )

    for key, value in report.scope_breakdown.model_dump().items():
        writer.writerow(("scopes", key, _labelize(key), value, "tCO2e"))

    benchmark = report.benchmark.model_dump() if report.benchmark else {}
    for key, value in benchmark.items():
        unit = "tCO2e" if isinstance(value, (int, float)) else ""
        writer.writerow(("benchmark", key, _labelize(key), value, unit))

    for key, value in report.offset_portfolio.model_dump().items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                writer.writerow(("offsets", f"{key}.{subkey}", _labelize(f"{key} {subkey}"), subvalue, "tCO2e"))
        else:
            unit = "usd" if "cost" in key else ("pct" if key.endswith("_pct") else "tCO2e")
            writer.writerow(("offsets", key, _labelize(key), value, unit))

    writer.writerow(("compliance", "overall_score_pct", "Overall Score", report.compliance.overall_score_pct, "pct"))
    writer.writerow(("compliance", "penalty_risk_usd", "Penalty Risk", report.compliance.penalty_risk_usd, "usd"))
    for framework in report.compliance.mandatory_frameworks:
        writer.writerow(("compliance_mandatory", framework, framework, framework, ""))
    for index, check in enumerate(report.compliance.checks, start=1):
        prefix = f"check_{index}"
        writer.writerow(("compliance_check", f"{prefix}.framework", "Framework", check.framework, ""))
        writer.writerow(("compliance_check", f"{prefix}.status", f"{check.framework} status", check.status, ""))
        writer.writerow(("compliance_check", f"{prefix}.score_pct", f"{check.framework} score", check.score_pct, "pct"))
        for gap_idx, gap in enumerate(check.gaps, start=1):
            if gap:
                writer.writerow(("compliance_gap", f"{prefix}.gap_{gap_idx}", f"{check.framework} gap", gap, ""))
        for rec_idx, rec in enumerate(check.recommendations, start=1):
            writer.writerow(("compliance_recommendation", f"{prefix}.recommendation_{rec_idx}", f"{check.framework} recommendation", rec, ""))

    for key, value in report.assumptions.items():
        writer.writerow(("assumptions", key, _labelize(key), value, ""))

    for key, value in report.factor_snapshot.items():
        unit = ""
        if isinstance(value, (int, float)):
            if "usd" in key:
                unit = "usd"
            elif "pct" in key:
                unit = "pct"
        writer.writerow(("factors", key, _labelize(key), value, unit))

    return buf.getvalue().encode("utf-8")


def _scenario_report_xlsx(report: ScenarioReportPayload):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font

    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Report Summary"
    summary_ws.append(["Field", "Value"])
    _style_header(summary_ws)

    scenario = report.scenario
    emissions = scenario["emissions"]
    for label, value in [
        ("Scenario", scenario["name"]),
        ("Event", scenario["event_name"]),
        ("Location", scenario["location"]),
        ("Event Type", scenario["event_type"]),
        ("Attendees", scenario["attendees"]),
        ("Event Days", scenario["event_days"]),
        ("Mode", scenario.get("mode", "")),
        ("Exported At", report.exported_at),
        ("Compliance Region", report.compliance_overrides.region),
        ("Has Scope 3", report.compliance_overrides.has_scope3),
        ("Has GHG Report", report.compliance_overrides.has_ghg_report),
        ("Total tCO2e", emissions["total_tco2e"]),
        ("Per Attendee tCO2e", emissions["per_attendee_tco2e"]),
        ("Per Attendee Day tCO2e", emissions["per_attendee_day_tco2e"]),
        ("Data Quality", emissions["data_quality"]),
        ("Overall Compliance Score", report.compliance.overall_score_pct),
        ("Offset Coverage %", report.offset_portfolio.coverage_pct if report.offset_portfolio.coverage_pct is not None else "—"),
    ]:
        summary_ws.append([label, value])

    summary_ws.append([])
    summary_ws.append(["Category", "tCO2e", "% of Total"])
    _style_header(summary_ws, summary_ws.max_row)
    categories_start = summary_ws.max_row + 1
    for category in report.categories:
        summary_ws.append([category.label, category.value, category.pct_total if category.pct_total is not None else ""])

    if report.categories:
        chart = BarChart()
        chart.type = "col"
        chart.title = "Emissions by Category"
        chart.y_axis.title = "tCO2e"
        data = Reference(summary_ws, min_col=2, min_row=categories_start, max_row=summary_ws.max_row)
        labels = Reference(summary_ws, min_col=1, min_row=categories_start, max_row=summary_ws.max_row)
        chart.add_data(data, titles_from_data=False)
        chart.set_categories(labels)
        chart.width = 12
        chart.height = 8
        summary_ws.add_chart(chart, "E4")

    compliance_ws = wb.create_sheet("Compliance")
    compliance_ws.append(["Framework", "Status", "Score %", "Gaps", "Recommendations"])
    _style_header(compliance_ws)
    for check in report.compliance.checks:
        compliance_ws.append([
            check.framework,
            check.status,
            check.score_pct,
            "\n".join([gap for gap in check.gaps if gap]),
            "\n".join(check.recommendations),
        ])

    offsets_ws = wb.create_sheet("Offsets")
    offsets_ws.append(["Metric", "Value"])
    _style_header(offsets_ws)
    for key, value in report.offset_portfolio.model_dump().items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                offsets_ws.append([_labelize(f"{key} {subkey}"), subvalue])
        else:
            offsets_ws.append([_labelize(key), value])

    factors_ws = wb.create_sheet("Factors")
    factors_ws.append(["Key", "Value"])
    _style_header(factors_ws)
    for key, value in report.factor_snapshot.items():
        factors_ws.append([key, value])

    assumptions_ws = wb.create_sheet("Assumptions")
    assumptions_ws.append(["Key", "Value"])
    _style_header(assumptions_ws)
    if report.assumptions:
        for key, value in report.assumptions.items():
            assumptions_ws.append([key, value])
    else:
        assumptions_ws.append(["notes", "No assumptions recorded"])

    for ws in wb.worksheets:
        for column in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in column), default=0)
            ws.column_dimensions[column[0].column_letter].width = min(max_len + 4, 48)
        if ws.title == "Report Summary":
            ws["A1"].font = Font(bold=True)

    return wb


def _scenario_report_pdf(report: ScenarioReportPayload) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#1A9E6E")))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], textColor=colors.HexColor("#1f6f6d")))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontSize=9, leading=12))

    def _table(rows: list[list[Any]], col_widths: Optional[list[float]] = None) -> Table:
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A9E6E")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    scenario = report.scenario
    emissions = scenario["emissions"]
    benchmark = report.benchmark.model_dump() if report.benchmark else None
    offset_summary = report.offset_portfolio.model_dump()
    factor_rows = [["Factor", "Value"]]
    for key, value in report.factor_snapshot.items():
        factor_rows.append([_labelize(key), str(value)])

    assumption_paragraphs = [
        Paragraph(f"<b>{_labelize(key)}:</b> {value}", styles["BodySmall"])
        for key, value in report.assumptions.items()
    ]

    story = [
        Paragraph(report.report_title, styles["ReportTitle"]),
        Spacer(1, 0.35 * cm),
        Paragraph(f"Generated {report.exported_at}", styles["BodyText"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"{scenario['name']} in {scenario['location']} covers {scenario['attendees']} attendees across "
            f"{scenario['event_days']} day(s). Total modeled emissions are {emissions['total_tco2e']:.3f} tCO2e.",
            styles["BodyText"],
        ),
        Spacer(1, 0.35 * cm),
        _table(
            [
                ["Field", "Value"],
                ["Scenario", scenario["name"]],
                ["Event", scenario["event_name"]],
                ["Event Type", _labelize(scenario["event_type"])],
                ["Attendees", scenario["attendees"]],
                ["Event Days", scenario["event_days"]],
                ["Data Quality", emissions["data_quality"]],
                ["Compliance Region", report.compliance_overrides.region],
            ],
            [5 * cm, 11 * cm],
        ),
        Spacer(1, 0.35 * cm),
        Paragraph(f"<b>Methodology:</b> {report.methodology}", styles["BodySmall"]),
        Spacer(1, 0.15 * cm),
        Paragraph(f"<b>Disclaimer:</b> {report.disclaimer}", styles["BodySmall"]),
        PageBreak(),
        Paragraph("Emissions by Category", styles["SectionHeading"]),
        Spacer(1, 0.2 * cm),
        _table(
            [["Category", "tCO2e", "% of Total"]]
            + [
                [category.label, f"{category.value:.4f}", f"{category.pct_total:.1f}%" if category.pct_total is not None else "—"]
                for category in report.categories
            ],
            [7 * cm, 3 * cm, 3 * cm],
        ),
        Spacer(1, 0.35 * cm),
        Paragraph("Scope Breakdown", styles["SectionHeading"]),
        Spacer(1, 0.2 * cm),
        _table(
            [["Scope", "tCO2e"]]
            + [[_labelize(key), f"{value:.4f}"] for key, value in report.scope_breakdown.model_dump().items()],
            [8 * cm, 3 * cm],
        ),
        Spacer(1, 0.35 * cm),
    ]

    if benchmark:
        story.extend(
            [
                Paragraph("Benchmark", styles["SectionHeading"]),
                Spacer(1, 0.2 * cm),
                _table(
                    [["Metric", "Value"]] + [[_labelize(key), value] for key, value in benchmark.items()],
                    [8 * cm, 6 * cm],
                ),
                Spacer(1, 0.35 * cm),
            ]
        )

    story.extend(
        [
            Paragraph("Compliance Status", styles["SectionHeading"]),
            Spacer(1, 0.2 * cm),
            _table(
                [["Framework", "Status", "Score %"]]
                + [[check.framework, check.status, f"{check.score_pct:.1f}"] for check in report.compliance.checks],
                [8 * cm, 4 * cm, 2.5 * cm],
            ),
            Spacer(1, 0.35 * cm),
            Paragraph("Offset Coverage", styles["SectionHeading"]),
            Spacer(1, 0.2 * cm),
            _table(
                [["Metric", "Value"]]
                + [[_labelize(key), value] for key, value in offset_summary.items() if not isinstance(value, dict)],
                [8 * cm, 6 * cm],
            ),
            Spacer(1, 0.35 * cm),
            Paragraph("Factor Provenance", styles["SectionHeading"]),
            Spacer(1, 0.2 * cm),
            _table(factor_rows[:9], [8 * cm, 6 * cm]),
        ]
    )

    if assumption_paragraphs:
        story.extend([Spacer(1, 0.35 * cm), Paragraph("Assumptions", styles["SectionHeading"])])
        for paragraph in assumption_paragraphs[:8]:
            story.extend([Spacer(1, 0.1 * cm), paragraph])

    doc.build(story)
    return buf.getvalue()


@router.get("/scenarios.xlsx", summary="Download all scenarios as Excel")
async def export_scenarios_xlsx(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    from openpyxl import Workbook

    q = (
        select(ScenarioDB)
        .where(ScenarioDB.user_id == current_user.id)
        .order_by(desc(ScenarioDB.created_at))
    )
    rows = (await db.execute(q)).scalars().all()

    wb = Workbook()

    ws = wb.active
    ws.title = "Scenarios"
    headers = [
        "ID", "Name", "Location", "Event Type", "Attendees", "Days", "Mode",
        "Travel tCO2e", "Venue Energy tCO2e", "Accommodation tCO2e",
        "Catering tCO2e", "Materials & Waste tCO2e",
        "Total tCO2e", "Per Attendee tCO2e",
        "Scope 1", "Scope 2", "Scope 3",
        "Data Quality", "Created At",
    ]
    ws.append(headers)
    _style_header(ws)
    for s in rows:
        ws.append([
            s.id, s.name, _scenario_location(s),
            s.event_type, s.attendees, s.event_days, s.mode,
            round(s.travel_tco2e or 0, 4),
            round(s.venue_energy_tco2e or 0, 4),
            round(s.accommodation_tco2e or 0, 4),
            round(s.catering_tco2e or 0, 4),
            round(s.materials_waste_tco2e or 0, 4),
            round(s.total_tco2e or 0, 4),
            round(s.per_attendee_tco2e or 0, 4),
            round(s.scope1_tco2e or 0, 4),
            round(s.scope2_tco2e or 0, 4),
            round(s.scope3_tco2e or 0, 4),
            s.data_quality,
            s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
        ])

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    ws2 = wb.create_sheet("Input Payloads")
    ws2.append(["Scenario ID", "Scenario Name", "Input Payload (JSON)"])
    _style_header(ws2)
    for s in rows:
        ws2.append([s.id, s.name, json.dumps(s.input_payload or {}, indent=2)])
    ws2.column_dimensions["A"].width = 36
    ws2.column_dimensions["B"].width = 30
    ws2.column_dimensions["C"].width = 80

    filename = f"cutcarbon_scenarios_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _wb_response(wb, filename)


@router.get("/scenarios/{scenario_id}.json", response_model=ScenarioReportPayload, summary="Download single scenario report package as JSON")
async def export_scenario_json(
    scenario_id: str,
    region: str = "singapore",
    has_scope3: bool = True,
    has_ghg_report: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    report = await build_scenario_report_payload(
        scenario_id=scenario_id,
        db=db,
        current_user=current_user,
        region=region,
        has_scope3=has_scope3,
        has_ghg_report=has_ghg_report,
    )
    return JSONResponse(
        content=report.model_dump(),
        headers={"Content-Disposition": f'attachment; filename="{_scenario_report_filename("cutcarbon_report", scenario_id, "json")}"'},
    )


@router.get("/scenarios/{scenario_id}.csv", summary="Download single scenario report package as CSV")
async def export_scenario_csv(
    scenario_id: str,
    region: str = "singapore",
    has_scope3: bool = True,
    has_ghg_report: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    report = await build_scenario_report_payload(
        scenario_id=scenario_id,
        db=db,
        current_user=current_user,
        region=region,
        has_scope3=has_scope3,
        has_ghg_report=has_ghg_report,
    )
    return _csv_response(
        _scenario_report_csv_bytes(report),
        _scenario_report_filename("cutcarbon_report", scenario_id, "csv"),
    )


@router.get("/scenarios/{scenario_id}.xlsx", summary="Download single scenario report package as Excel")
async def export_scenario_xlsx(
    scenario_id: str,
    region: str = "singapore",
    has_scope3: bool = True,
    has_ghg_report: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    report = await build_scenario_report_payload(
        scenario_id=scenario_id,
        db=db,
        current_user=current_user,
        region=region,
        has_scope3=has_scope3,
        has_ghg_report=has_ghg_report,
    )
    wb = _scenario_report_xlsx(report)
    return _wb_response(wb, _scenario_report_filename("cutcarbon_report", scenario_id, "xlsx"))


@router.get("/scenarios/{scenario_id}.pdf", summary="Download single scenario report package as PDF")
async def export_scenario_pdf(
    scenario_id: str,
    region: str = "singapore",
    has_scope3: bool = True,
    has_ghg_report: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    report = await build_scenario_report_payload(
        scenario_id=scenario_id,
        db=db,
        current_user=current_user,
        region=region,
        has_scope3=has_scope3,
        has_ghg_report=has_ghg_report,
    )
    return _pdf_response(
        _scenario_report_pdf(report),
        _scenario_report_filename("cutcarbon_report", scenario_id, "pdf"),
    )


@router.get("/emission-factors.xlsx", summary="Download emission factor catalog as Excel")
async def export_emission_factors_xlsx():
    from openpyxl import Workbook

    ef_path = _DATA_DIR / "emission_factors.json"
    with open(ef_path) as f:
        ef = json.load(f)

    wb = Workbook()
    ws = wb.active
    ws.title = "Emission Factors"
    ws.append(["Category", "Subcategory / Key", "Region", "Factor / Value", "Unit", "Source", "Last Fetched"])
    _style_header(ws)

    def _flatten(data, prefix=""):
        for k, v in data.items():
            if k.startswith("_") or k == "last_agent_update":
                continue
            if isinstance(v, dict):
                if "factor" in v or "economy" in v or "factor_value" in v:
                    factor = v.get("factor") or v.get("economy") or v.get("factor_value", "")
                    ws.append([
                        prefix, k,
                        v.get("region", ""),
                        factor,
                        v.get("unit", ""),
                        v.get("source", ""),
                        v.get("last_fetched", ""),
                    ])
                else:
                    _flatten(v, prefix=f"{prefix}/{k}" if prefix else k)
            elif isinstance(v, (int, float)):
                ws.append([prefix, k, "", v, "", "", ""])

    _flatten(ef)

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 45)

    filename = f"cutcarbon_emission_factors_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _wb_response(wb, filename)


@router.get("/agent-runs.xlsx", summary="Download TinyFish agent run history as Excel")
async def export_agent_runs_xlsx(
    db: AsyncSession = Depends(get_db),
    limit: int = 500,
    current_user: UserDB = Depends(get_current_user),
):
    from openpyxl import Workbook

    rows = (
        await db.execute(
            select(AgentRunDB).order_by(desc(AgentRunDB.fetched_at)).limit(limit)
        )
    ).scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Agent Runs"
    ws.append(["ID", "Agent Name", "Category", "Status", "Run ID", "Steps", "Source URL", "Fetched At", "Error", "Data (JSON)"])
    _style_header(ws)

    for r in rows:
        ws.append([
            r.id, r.agent_name, r.category, r.status,
            r.run_id or "", r.num_steps or "",
            r.source_url or "",
            r.fetched_at.strftime("%Y-%m-%d %H:%M:%S") if r.fetched_at else "",
            r.error or "",
            json.dumps(r.result_json or {}),
        ])

    col_widths = [6, 22, 16, 10, 36, 8, 55, 20, 30, 60]
    for i, width in enumerate(col_widths, 1):
        from openpyxl.utils import get_column_letter

        ws.column_dimensions[get_column_letter(i)].width = width

    filename = f"cutcarbon_agent_runs_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _wb_response(wb, filename)


@router.get("/emission-factors.json", summary="Download emission_factors.json (raw)")
async def export_emission_factors_json():
    ef_path = _DATA_DIR / "emission_factors.json"
    with open(ef_path) as f:
        data = json.load(f)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="emission_factors_{datetime.utcnow().strftime("%Y%m%d")}.json"'},
    )


@router.get("/scenarios.json", summary="Download all scenarios as raw JSON")
async def export_scenarios_json(
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    q = (
        select(ScenarioDB)
        .where(ScenarioDB.user_id == current_user.id)
        .order_by(desc(ScenarioDB.created_at))
    )
    rows = (await db.execute(q)).scalars().all()

    data = [_serialize_scenario_row(s) for s in rows]
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="cutcarbon_scenarios_{datetime.utcnow().strftime("%Y%m%d")}.json"'},
    )
