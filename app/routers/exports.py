"""
Data export router — download raw or processed data as Excel (.xlsx) or JSON.

Endpoints:
  GET /api/exports/scenarios.xlsx         — All scenarios for the logged-in user
  GET /api/exports/scenarios/{id}.xlsx    — Single scenario full report
  GET /api/exports/emission-factors.xlsx  — Current emission factor catalog
  GET /api/exports/agent-runs.xlsx        — TinyFish agent run history
  GET /api/exports/scenarios.json         — All scenarios as JSON (raw)
"""
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, ScenarioDB, AgentRunDB, UserDB
from app.routers.auth import get_current_user

router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"


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
    from openpyxl.styles import Font, PatternFill, Alignment
    fill = PatternFill("solid", fgColor="1A9E6E")
    for cell in ws[row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")


# ── /scenarios.xlsx ────────────────────────────────────────────────────────────

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

    # Sheet 1: Summary
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
            s.id, s.name, getattr(s, "location", None) or (s.input_payload or {}).get("location", ""),
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

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    # Sheet 2: Assumptions / input payloads
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


# ── /scenarios/{id}.xlsx ───────────────────────────────────────────────────────

@router.get("/scenarios/{scenario_id}.xlsx", summary="Download single scenario report as Excel")
async def export_scenario_xlsx(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.chart import BarChart, Reference

    s = await db.scalar(
        select(ScenarioDB).where(
            ScenarioDB.id == scenario_id,
            ScenarioDB.user_id == current_user.id,
        )
    )
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")

    wb = Workbook()
    ws = wb.active
    ws.title = "Emissions Report"

    # Title block
    ws.merge_cells("A1:C1")
    ws["A1"] = f"Carbon Footprint Report — {s.name}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].fill = PatternFill("solid", fgColor="1A9E6E")
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    ws["A2"] = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    ws["A2"].font = Font(italic=True, color="6B7280")

    # Metadata
    meta = [
        ("Location", getattr(s, "location", None) or (s.input_payload or {}).get("location", "")),
        ("Event Type", s.event_type),
        ("Attendees", s.attendees),
        ("Event Days", s.event_days),
        ("Mode", s.mode),
        ("Data Quality", s.data_quality),
        ("Created", s.created_at.strftime("%Y-%m-%d") if s.created_at else ""),
    ]
    for i, (k, v) in enumerate(meta, start=4):
        ws[f"A{i}"] = k
        ws[f"A{i}"].font = Font(bold=True)
        ws[f"B{i}"] = v

    # Emissions breakdown table
    ws["A11"] = "Emissions Breakdown"
    ws["A11"].font = Font(bold=True, size=12)
    ws.append([])
    breakdown = [
        ("Travel", s.travel_tco2e),
        ("Venue Energy", s.venue_energy_tco2e),
        ("Accommodation", s.accommodation_tco2e),
        ("Catering", s.catering_tco2e),
        ("Materials & Waste", s.materials_waste_tco2e),
    ]
    ws.append(["Category", "tCO2e", "% of Total"])
    _style_header(ws, ws.max_row)
    total = s.total_tco2e or 1
    for cat, val in breakdown:
        pct = round((val or 0) / total * 100, 1) if total else 0
        ws.append([cat, round(val or 0, 4), f"{pct}%"])

    ws.append(["TOTAL", round(s.total_tco2e or 0, 4), "100%"])
    ws[f"A{ws.max_row}"].font = Font(bold=True)
    ws[f"B{ws.max_row}"].font = Font(bold=True)
    ws.append(["Per Attendee", round(s.per_attendee_tco2e or 0, 4), ""])

    # Scope breakdown
    ws.append([])
    ws.append(["GHG Protocol Scope Breakdown"])
    ws[f"A{ws.max_row}"].font = Font(bold=True, size=12)
    ws.append(["Scope", "tCO2e"])
    _style_header(ws, ws.max_row)
    for label, val in [("Scope 1 (Direct)", s.scope1_tco2e), ("Scope 2 (Energy)", s.scope2_tco2e), ("Scope 3 (Indirect)", s.scope3_tco2e)]:
        ws.append([label, round(val or 0, 4)])

    # Bar chart for category breakdown
    chart = BarChart()
    chart.type = "col"
    chart.title = "Emissions by Category (tCO2e)"
    chart.y_axis.title = "tCO2e"
    chart.x_axis.title = "Category"
    chart.shape = 4
    chart_data = Reference(ws, min_col=2, min_row=13, max_row=17)
    cats = Reference(ws, min_col=1, min_row=13, max_row=17)
    chart.add_data(chart_data, titles_from_data=False)
    chart.set_categories(cats)
    chart.width = 18
    chart.height = 12
    ws.add_chart(chart, "E4")

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 36)

    filename = f"cutcarbon_report_{scenario_id}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _wb_response(wb, filename)


# ── /emission-factors.xlsx ─────────────────────────────────────────────────────

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


# ── /agent-runs.xlsx ───────────────────────────────────────────────────────────

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
    for i, w in enumerate(col_widths, 1):
        from openpyxl.utils import get_column_letter
        ws.column_dimensions[get_column_letter(i)].width = w

    filename = f"cutcarbon_agent_runs_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _wb_response(wb, filename)


# ── /scenarios.json ────────────────────────────────────────────────────────────

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

    data = [
        {
            "scenario_id": s.id,
            "name": s.name,
            "location": getattr(s, "location", None) or (s.input_payload or {}).get("location"),
            "event_type": s.event_type,
            "attendees": s.attendees,
            "event_days": s.event_days,
            "mode": s.mode,
            "emissions": {
                "travel_tco2e": s.travel_tco2e,
                "venue_energy_tco2e": s.venue_energy_tco2e,
                "accommodation_tco2e": s.accommodation_tco2e,
                "catering_tco2e": s.catering_tco2e,
                "materials_waste_tco2e": s.materials_waste_tco2e,
                "total_tco2e": s.total_tco2e,
                "per_attendee_tco2e": s.per_attendee_tco2e,
                "scope1_tco2e": s.scope1_tco2e,
                "scope2_tco2e": s.scope2_tco2e,
                "scope3_tco2e": s.scope3_tco2e,
            },
            "data_quality": s.data_quality,
            "input_payload": s.input_payload,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="cutcarbon_scenarios_{datetime.utcnow().strftime("%Y%m%d")}.json"'},
    )
