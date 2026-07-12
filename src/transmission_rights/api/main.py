import csv
import json
from functools import lru_cache
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Query

from transmission_rights.api.discovery import router as discovery_router
from transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher
from transmission_rights.config import settings
from transmission_rights.data.contracts import build_example_product
from transmission_rights.domain.models import AllocationType, FairValueRequest, PortfolioPosition, SRAProduct, ValuationInputs
from transmission_rights.services.valuation import FairValueEngine
from transmission_rights.services.aemo.fill_rate_fair_value_engine import FillRateFairValueEngine
from transmission_rights.services.aemo.market_analytics import (
    correlation_summary,
    load_market_frame,
    sequential_backtest_summary,
    trend_summary,
)
from transmission_rights.services.aemo.recommendation_ledger import RecommendationLedger, RecommendationRecord
import pandas as pd


def utc_now_iso() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.utcnow().isoformat() + "Z"

app = FastAPI(title="HaimOS Transmission Rights", version="0.1.0")
app.include_router(discovery_router)

engine = FairValueEngine()
fill_rate_engine = FillRateFairValueEngine()
FAIR_VALUE_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "derived" / "fair_value"
RAW_SRA_RESULTS_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "aemo" / "sra_results"
LEDGER_DIR = Path(__file__).resolve().parents[3] / "data" / "derived" / "recommendation_ledger"
recommendation_ledger = RecommendationLedger(LEDGER_DIR)


def _read_csv_rows(path: Path, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if index >= limit:
                break
            rows.append({key: str(value) for key, value in row.items()})
    return rows


def _other_region(interconnector_id: str, from_region: str) -> str:
    if "-" not in interconnector_id:
        return ""
    left, right = interconnector_id.split("-", 1)
    if from_region == left:
        return right
    if from_region == right:
        return left
    return ""


def _quarter_bounds(quarter: str) -> tuple[date | None, date | None]:
    try:
        if len(quarter) < 7 or not quarter.startswith("C") or "Q" not in quarter:
            return None, None
        year = int(quarter[1:5])
        q = int(quarter[-1])
        quarter_starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        quarter_ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        if q not in quarter_starts:
            return None, None
        start_month, start_day = quarter_starts[q]
        end_month, end_day = quarter_ends[q]
        return date(year, start_month, start_day), date(year, end_month, end_day)
    except Exception:
        return None, None


def _quarter_time_scales(quarter: str, as_of: date | None = None) -> dict:
    """Return rich time-scale metadata for an SRA quarter.

    SRA settlement note
    -------------------
    Holders of SRA units are paid for EVERY 5-minute dispatch interval
    that the interconnector flows in the direction of the right.
    Each quarter contains ~26,208 dispatch intervals (91 days × 288 intervals/day).
    Actual payment = Σ (spot_price_from − spot_price_to) over all flowing intervals,
    capped to 0 per interval (you don't pay when flow is reversed).
    The quoted market_price_aud reflects the market's expectation of that sum.
    """
    today = as_of or datetime.utcnow().date()
    start_date, end_date = _quarter_bounds(quarter)
    if not start_date or not end_date:
        return {}
    calendar_days = (end_date - start_date).days + 1
    intervals_per_day = 288          # 24 h × 12 × (5-min intervals)
    total_intervals = calendar_days * intervals_per_day
    # Conservative: assume 85% of intervals the interconnector is flowing your direction
    expected_paying_intervals = round(total_intervals * 0.85)
    days_to_start = max((start_date - today).days, 0)
    days_remaining = max((end_date - today).days, 0)
    quarter_started = today >= start_date
    return {
        "quarter_start": start_date.isoformat(),
        "quarter_end":   end_date.isoformat(),
        "calendar_days": calendar_days,
        "days_to_start": days_to_start,
        "days_remaining": days_remaining,
        "total_5min_intervals": total_intervals,
        "expected_paying_intervals": expected_paying_intervals,
        "quarter_started": quarter_started,
        "settlement_mechanics": (
            "SRA pays every 5-min dispatch interval where the interconnector flows in your direction. "
            f"This quarter has {total_intervals:,} intervals ({calendar_days} days × 288/day). "
            f"Assuming ~85% directional flow ≈ {expected_paying_intervals:,} paying intervals. "
            "Payment per interval = max(0, RRP_from − RRP_to) × units_held. "
            "You are NOT paid for reverse-flow intervals — you simply receive $0 for those."
        ),
    }


def _quarter_progress_pct(quarter: str, as_of: date | None = None) -> float:
    start_date, end_date = _quarter_bounds(quarter)
    if not start_date or not end_date:
        return 0.0
    today = as_of or datetime.utcnow().date()
    if today <= start_date:
        return 0.0
    if today >= end_date:
        return 100.0
    elapsed = (today - start_date).days
    total = max((end_date - start_date).days, 1)
    return round((elapsed / total) * 100.0, 1)


def _recommendation(fair_value: float, market_value: float) -> tuple[str, str]:
    if market_value <= 0:
        return "WATCH", "No market price available"
    discount_pct = (fair_value - market_value) / market_value * 100.0
    if discount_pct >= 12:
        return "BUY", f"Fair value is {discount_pct:.1f}% above market"
    if discount_pct >= 4:
        return "HOLD", f"Fair value is {discount_pct:.1f}% above market"
    if discount_pct <= -8:
        return "AVOID", f"Fair value is {abs(discount_pct):.1f}% below market"
    return "WATCH", f"Fair value is {abs(discount_pct):.1f}% from market"


def _percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 50.0
    less_or_equal = sum(1 for item in values if item <= value)
    return round((less_or_equal / len(values)) * 100.0, 2)


def _source_file_rank(filename: str) -> tuple[str, str]:
    stem = filename.replace(".csv", "")
    suffix = stem.split("_")[-1]
    if len(suffix) >= 14 and suffix[-14:].isdigit():
        ts = suffix[-14:]
        seq = suffix[:-14] or "0"
        return ts, seq
    return "00000000000000", "0"


def _candidate_key(row: dict[str, object]) -> tuple[str, str, str, int, str, str]:
    return (
        str(row.get("product_id") or ""),
        str(row.get("contract_id") or ""),
        str(row.get("quarter") or ""),
        int(row.get("tranche_no") or 0),
        str(row.get("interconnector") or ""),
        str(row.get("direction_label") or f"{row.get('from_region', '')}→{row.get('to_region', '')}"),
    )


def _execution_limits(
    row: dict[str, object],
    risk_budget_aud: float,
    max_participation_pct: float,
) -> dict[str, float | int]:
    market_price = max(float(row.get("market_price_start_qtr_aud", 0.0) or 0.0), 0.0)
    arb_per_unit = abs(float(row.get("arbitrage_per_unit_aud", 0.0) or 0.0))
    stop_per_unit = max(arb_per_unit * 0.5, market_price * 0.05, 1.0)

    units_sold = max(int(row.get("units_sold", 0) or 0), 0)
    units_offered = max(int(row.get("units_offered", 0) or 0), 0)
    liquidity_basis_units = max(units_sold, units_offered, 1)
    max_no_impact_units = max(1, int(liquidity_basis_units * (max_participation_pct / 100.0)))
    if units_offered > 0:
        max_no_impact_units = min(max_no_impact_units, units_offered)

    risk_units = int(max(1, risk_budget_aud // stop_per_unit))
    suggested_units = min(risk_units, max_no_impact_units)
    if units_offered > 0:
        suggested_units = min(suggested_units, units_offered)

    max_no_impact_spend_aud = round(max_no_impact_units * market_price, 2)
    suggested_spend_aud = round(suggested_units * market_price, 2)
    liquidity_participation_pct = round((suggested_units / liquidity_basis_units) * 100.0, 2)

    return {
        "market_price_aud": market_price,
        "risk_per_unit_aud": round(stop_per_unit, 2),
        "max_no_impact_units": max_no_impact_units,
        "max_no_impact_spend_aud": max_no_impact_spend_aud,
        "suggested_units": suggested_units,
        "suggested_spend_aud": suggested_spend_aud,
        "liquidity_basis_units": liquidity_basis_units,
        "liquidity_participation_pct": liquidity_participation_pct,
    }


def _build_trade_candidates(
    rows: list[dict[str, object]],
    min_confidence: float,
    min_edge_pct: float,
    risk_budget_aud: float,
    max_participation_pct: float,
    side_filter: set[str] | None = None,
) -> list[dict[str, object]]:
    best_by_key: dict[tuple[str, str, str, int, str, str], dict[str, object]] = {}

    for row in rows:
        confidence = float(row.get("recommendation_confidence", 0.0) or 0.0)
        edge_pct = abs(float(row.get("fair_premium_pct", 0.0) or 0.0))
        if confidence < min_confidence or edge_pct < min_edge_pct:
            continue

        side = str(row.get("arbitrage_side", "NEUTRAL"))
        if side == "NEUTRAL":
            continue
        if side_filter and side not in side_filter:
            continue

        sizing = _execution_limits(
            row=row,
            risk_budget_aud=risk_budget_aud,
            max_participation_pct=max_participation_pct,
        )
        market_price = float(sizing["market_price_aud"])
        suggested_units = int(sizing["suggested_units"])
        signed_per_unit_edge = float(row.get("arbitrage_per_unit_aud", 0.0) or 0.0)
        expected_edge_aud = round(abs(signed_per_unit_edge) * suggested_units, 2)
        expected_edge_per_dollar = round(
            (expected_edge_aud / float(sizing["suggested_spend_aud"])) if float(sizing["suggested_spend_aud"]) > 0 else 0.0,
            6,
        )
        trade_action = "BUY_CALLS" if side == "LONG" else "BUY_PUTS"

        qtr_scales = _quarter_time_scales(str(row.get("quarter") or ""))
        candidate = {
            "product_id": row.get("product_id"),
            "contract_id": row.get("contract_id"),
            "quarter": row.get("quarter"),
            "tranche_no": row.get("tranche_no"),
            "interconnector": row.get("interconnector"),
            "direction": row.get("direction_label") or f"{row.get('from_region')}→{row.get('to_region')}",
            "trade_action": trade_action,
            "side": side,
            "market_price_aud": market_price,
            "fair_value_aud": float(row.get("fair_value_per_unit_aud", 0.0) or 0.0),
            "delta_edge_pct": round(float(row.get("fair_premium_pct", 0.0) or 0.0), 2),
            "arbitrage_per_unit_aud": round(float(row.get("arbitrage_per_unit_aud", 0.0) or 0.0), 2),
            "signed_edge_per_unit_aud": round(signed_per_unit_edge, 2),
            "confidence": round(confidence, 3),
            "suggested_units": suggested_units,
            "risk_per_unit_aud": float(sizing["risk_per_unit_aud"]),
            "expected_edge_aud": expected_edge_aud,
            "expected_edge_per_dollar": expected_edge_per_dollar,
            "max_no_impact_units": int(sizing["max_no_impact_units"]),
            "max_no_impact_spend_aud": float(sizing["max_no_impact_spend_aud"]),
            "suggested_spend_aud": float(sizing["suggested_spend_aud"]),
            "liquidity_basis_units": int(sizing["liquidity_basis_units"]),
            "liquidity_participation_pct": float(sizing["liquidity_participation_pct"]),
            "recommendation": row.get("recommendation"),
            "recommendation_reason": row.get("recommendation_reason"),
            # Time-scale fields
            "quarter_start": qtr_scales.get("quarter_start"),
            "quarter_end": qtr_scales.get("quarter_end"),
            "calendar_days": qtr_scales.get("calendar_days"),
            "days_to_start": qtr_scales.get("days_to_start"),
            "days_remaining": qtr_scales.get("days_remaining"),
            "total_5min_intervals": qtr_scales.get("total_5min_intervals"),
            "expected_paying_intervals": qtr_scales.get("expected_paying_intervals"),
            "quarter_started": qtr_scales.get("quarter_started"),
            "settlement_mechanics": qtr_scales.get("settlement_mechanics"),
        }

        key = _candidate_key(row)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = candidate
            continue

        existing_edge = abs(float(existing.get("expected_edge_aud", 0.0) or 0.0))
        new_edge = abs(float(candidate.get("expected_edge_aud", 0.0) or 0.0))
        existing_conf = float(existing.get("confidence", 0.0) or 0.0)
        new_conf = float(candidate.get("confidence", 0.0) or 0.0)
        if (new_edge, new_conf) > (existing_edge, existing_conf):
            best_by_key[key] = candidate

    return list(best_by_key.values())


def _summarize_trade_groups(candidates: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    quarter_groups: dict[str, list[dict[str, object]]] = {}
    for item in candidates:
        quarter = str(item.get("quarter") or "Unknown")
        quarter_groups.setdefault(quarter, []).append(item)

    quarter_summaries: list[dict[str, object]] = []
    year_totals: dict[str, dict[str, float]] = {}

    for quarter in sorted(quarter_groups.keys()):
        items = quarter_groups[quarter]
        year = quarter[1:5] if len(quarter) >= 5 else "Unknown"
        quarter_start = items[0].get("quarter_start")
        quarter_end = items[0].get("quarter_end")
        total_spend = round(sum(float(item.get("suggested_spend_aud", 0.0) or 0.0) for item in items), 2)
        total_edge = round(sum(float(item.get("expected_edge_aud", 0.0) or 0.0) for item in items), 2)
        total_profit = round(sum(float(item.get("expected_edge_aud", 0.0) or 0.0) * float(item.get("confidence", 0.0) or 0.0) for item in items), 2)
        total_risk = round(sum(float(item.get("risk_per_unit_aud", 0.0) or 0.0) * int(item.get("suggested_units", 0) or 0) for item in items), 2)
        rorc = round((total_profit / total_risk) if total_risk > 0 else 0.0, 4)

        # Selling the whole quarter here means exiting the full proposed position at current market prices.
        sell_now_value = total_spend
        implied_exit_spread = round(total_edge - total_profit, 2)

        quarter_summary = {
            "year": year,
            "quarter": quarter,
            "quarter_start": quarter_start,
            "quarter_end": quarter_end,
            "count": len(items),
            "total_suggested_spend_aud": total_spend,
            "total_expected_edge_aud": total_edge,
            "total_projected_profit_aud": total_profit,
            "total_capital_at_risk_aud": total_risk,
            "return_on_risked_capital_pct": round(rorc * 100.0, 2),
            "sell_now_value_aud": sell_now_value,
            "implied_exit_spread_aud": implied_exit_spread,
            "notation": "Sell entire quarter = exit the full proposed position at current market value; not the same as quarter settlement payout.",
        }
        quarter_summaries.append(quarter_summary)

        bucket = year_totals.setdefault(year, {"spend": 0.0, "edge": 0.0, "profit": 0.0, "risk": 0.0, "count": 0.0})
        bucket["spend"] += total_spend
        bucket["edge"] += total_edge
        bucket["profit"] += total_profit
        bucket["risk"] += total_risk
        bucket["count"] += len(items)

    year_summaries: list[dict[str, object]] = []
    for year in sorted(year_totals.keys()):
        bucket = year_totals[year]
        year_rorc = round((bucket["profit"] / bucket["risk"]) if bucket["risk"] > 0 else 0.0, 4)
        year_summaries.append(
            {
                "year": year,
                "count": int(bucket["count"]),
                "total_suggested_spend_aud": round(bucket["spend"], 2),
                "total_expected_edge_aud": round(bucket["edge"], 2),
                "total_projected_profit_aud": round(bucket["profit"], 2),
                "total_capital_at_risk_aud": round(bucket["risk"], 2),
                "return_on_risked_capital_pct": round(year_rorc * 100.0, 2),
            }
        )

    return quarter_summaries, year_summaries


@lru_cache(maxsize=1)
def _load_product_mark_rows() -> list[dict[str, object]]:
    if not RAW_SRA_RESULTS_DIR.exists():
        return []

    fetcher = HistoricalDataFetcher()
    raw_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    for path in sorted(RAW_SRA_RESULTS_DIR.glob("*.csv")):
        try:
            csv_text = path.read_text(encoding="utf-8")
            snapshots = fetcher.parse_sra_results(csv_text)
        except Exception:
            continue

        for snapshot in snapshots:
            units_offered = max(int(snapshot.units_offered or 0), 1)
            units_sold = int(snapshot.units_sold or 0)
            fill_rate = units_sold / units_offered if units_offered > 0 else 0
            current_value_per_unit = float(snapshot.clearing_price or 0.0)
            key = (snapshot.contract_id, snapshot.directional_interconnector, snapshot.from_region)
            candidate = {
                "contract_id": snapshot.contract_id,
                "quarter": snapshot.quarter,
                "tranche_no": int(snapshot.tranche_no or 0),
                "interconnector": snapshot.directional_interconnector,
                "from_region": snapshot.from_region,
                "to_region": _other_region(snapshot.directional_interconnector, snapshot.from_region),
                "units_offered": units_offered,
                "units_sold": units_sold,
                "fill_rate": round(fill_rate, 6),
                "market_price_start_qtr_aud": round(current_value_per_unit, 2),
                "current_value_total_aud": round(current_value_per_unit * units_sold, 2),
                "source_file": path.name,
                "_source_rank": _source_file_rank(path.name),
            }

            prev = raw_by_key.get(key)
            if prev is None or candidate["_source_rank"] >= prev["_source_rank"]:
                raw_by_key[key] = candidate

    raw_rows = list(raw_by_key.values())
    if not raw_rows:
        return []

    fill_rates = [float(row["fill_rate"]) for row in raw_rows]
    volumes = [float(row["units_offered"]) for row in raw_rows]

    output_rows: list[dict[str, object]] = []
    for row in raw_rows:
        fill_rate_pct = _percentile_rank(fill_rates, float(row["fill_rate"]))
        volume_pct = _percentile_rank(volumes, float(row["units_offered"]))
        market_price = float(row["market_price_start_qtr_aud"])

        fr_result = fill_rate_engine.estimate_fair_value(
            market_price=market_price,
            fill_rate=float(row["fill_rate"]),
            units_offered=int(row["units_offered"]),
            fill_rate_percentile=fill_rate_pct,
            volume_percentile=volume_pct,
            interconnector_volatility=0.28,
        )

        fair_value_per_unit = float(fr_result.fair_value)
        units_sold = int(row["units_sold"])
        fair_value_total = round(fair_value_per_unit * units_sold, 2)
        recommendation, recommendation_reason = fill_rate_engine.get_recommendation(
            fair_value_per_unit, market_price, fr_result.confidence
        )

        market_share_of_fair_pct = round((market_price / fair_value_per_unit * 100.0), 1) if fair_value_per_unit else 0.0
        fair_premium_pct = round(((fair_value_per_unit - market_price) / market_price * 100.0), 1) if market_price else 0.0
        arbitrage_per_unit_aud = round(fair_value_per_unit - market_price, 2)
        arbitrage_total_aud = round(arbitrage_per_unit_aud * units_sold, 2)
        if fair_premium_pct >= 2.0:
            arbitrage_side = "LONG"
        elif fair_premium_pct <= -2.0:
            arbitrage_side = "SHORT"
        else:
            arbitrage_side = "NEUTRAL"

        output = {
            "product_id": f"{row['contract_id']}:{row['interconnector']}:{row['from_region']}",
            "contract_id": row["contract_id"],
            "quarter": row["quarter"],
            "tranche_no": row["tranche_no"],
            "interconnector": row["interconnector"],
            "from_region": row["from_region"],
            "to_region": row["to_region"],
            "direction_label": f"{row['from_region']}→{row['to_region']}",
            "units_offered": row["units_offered"],
            "units_sold": units_sold,
            "fill_rate": round(float(row["fill_rate"]), 3),
            "fill_rate_percentile": fill_rate_pct,
            "volume_percentile": volume_pct,
            "market_price_start_qtr_aud": round(market_price, 2),
            "current_value_total_aud": row["current_value_total_aud"],
            "fair_value_per_unit_aud": fair_value_per_unit,
            "fair_value_total_aud": fair_value_total,
            "spread_per_unit_aud": round(fair_value_per_unit - market_price, 2),
            "quarter_progress_pct": _quarter_progress_pct(str(row["quarter"])),
            "market_share_of_fair_pct": market_share_of_fair_pct,
            "fair_premium_pct": fair_premium_pct,
            "arbitrage_per_unit_aud": arbitrage_per_unit_aud,
            "arbitrage_total_aud": arbitrage_total_aud,
            "arbitrage_side": arbitrage_side,
            "recommendation": recommendation,
            "recommendation_reason": recommendation_reason,
            "recommendation_confidence": fr_result.confidence,
            "fill_rate_signal": fr_result.fill_rate_signal,
            "volume_signal": fr_result.volume_signal,
            "fair_value_model": fr_result.model_notes,
            "source_file": row["source_file"],
            "source_status": "latest",
        }
        output_rows.append(output)

        try:
            spread_per_unit = fair_value_per_unit - market_price
            spread_pct = (spread_per_unit / market_price * 100.0) if market_price else 0.0
            recommendation_ledger.append_recommendation(
                RecommendationRecord(
                    timestamp=utc_now_iso(),
                    product_id=f"{row['interconnector']}:{row['from_region']}",
                    quarter=str(row["quarter"]),
                    tranche=int(row["tranche_no"]),
                    market_price_aud=round(market_price, 2),
                    units_offered=int(row["units_offered"]),
                    units_sold=units_sold,
                    fill_rate=round(float(row["fill_rate"]), 6),
                    fair_value_aud=round(fair_value_per_unit, 2),
                    fair_value_model="fill_rate_based_v2_global_percentile",
                    fill_rate_percentile=round(fill_rate_pct, 2),
                    volume_percentile=round(volume_pct, 2),
                    recommendation=recommendation,
                    confidence=float(fr_result.confidence),
                    spread_aud=round(spread_per_unit, 2),
                    spread_pct=round(spread_pct, 2),
                    fill_rate_signal=float(fr_result.fill_rate_signal),
                    volume_signal=float(fr_result.volume_signal),
                )
            )
        except Exception:
            pass

    return sorted(
        output_rows,
        key=lambda row: (
            str(row["quarter"]),
            str(row["interconnector"]),
            int(row["tranche_no"]),
            str(row["from_region"]),
        ),
    )


@lru_cache(maxsize=1)
def _load_market_frame_cached() -> pd.DataFrame:
    return load_market_frame(RAW_SRA_RESULTS_DIR)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "timestamp": utc_now_iso(),
    }


@app.get("/products/example")
def example_product() -> dict:
    product = build_example_product()
    return {
        "product": product.model_dump(),
        "description": "Illustrative SRA product only; replace with controlled AEMO catalog ingestion.",
    }


@app.post("/valuation/fair-value")
def fair_value(request: FairValueRequest) -> dict:
    response = engine.value(request)
    return response.model_dump()


@app.get("/valuation/example")
def example_valuation() -> dict:
    product = build_example_product()
    request = FairValueRequest(
        product=product,
        position=PortfolioPosition(units_held=40, acquisition_price_per_unit=2500),
        inputs=ValuationInputs(
            expected_irsr=4_000_000,
            downside_irsr=2_800_000,
            upside_irsr=5_200_000,
            confidence_level=0.8,
            model_risk_discount=0.05,
            liquidity_discount=0.03,
        ),
    )
    return engine.value(request).model_dump()


@app.get("/ux/fair-value/summary")
def ux_fair_value_summary() -> dict:
    summary_path = FAIR_VALUE_OUTPUT_DIR / "fair_value_calibration_summary.json"
    if not summary_path.exists():
        return {
            "status": "missing",
            "message": "No fair-value calibration summary found yet.",
            "path": str(summary_path),
        }

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "status": "ok",
        "path": str(summary_path),
        "summary": summary,
    }


@app.get("/ux/fair-value/quarterly")
def ux_fair_value_quarterly(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    quarterly_path = FAIR_VALUE_OUTPUT_DIR / "fair_value_backtest_by_quarter.csv"
    if not quarterly_path.exists():
        return {
            "status": "missing",
            "message": "No quarter backtest output found yet.",
            "path": str(quarterly_path),
        }

    rows = _read_csv_rows(quarterly_path, limit=limit)
    return {
        "status": "ok",
        "path": str(quarterly_path),
        "rows": rows,
        "count": len(rows),
    }


@app.get("/ux/fair-value/diagnostics")
def ux_fair_value_diagnostics(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    diagnostics_path = FAIR_VALUE_OUTPUT_DIR / "fair_value_calibration_diagnostics.csv"
    if not diagnostics_path.exists():
        return {
            "status": "missing",
            "message": "No diagnostics output found yet.",
            "path": str(diagnostics_path),
        }

    rows = _read_csv_rows(diagnostics_path, limit=limit)
    return {
        "status": "ok",
        "path": str(diagnostics_path),
        "rows": rows,
        "count": len(rows),
    }


@app.get("/ux/fair-value/products")
def ux_fair_value_products(limit: int = Query(default=500, ge=1, le=1000)) -> dict:
    rows = _load_product_mark_rows()
    if not rows:
        product = build_example_product()
        response = engine.value(
            FairValueRequest(
                product=product,
                position=PortfolioPosition(units_held=1, acquisition_price_per_unit=2500),
                inputs=ValuationInputs(
                    expected_irsr=4_000_000,
                    downside_irsr=2_800_000,
                    upside_irsr=5_200_000,
                    confidence_level=0.8,
                    model_risk_discount=0.05,
                    liquidity_discount=0.03,
                ),
            )
        )
        rows = [{
            "product_id": product.interconnector_id,
            "contract_id": "example",
            "quarter": product.relevant_quarter,
            "tranche_no": product.tranche_no,
            "interconnector": product.interconnector_id,
            "from_region": product.direction_from_region,
            "to_region": product.direction_to_region,
            "units_offered": product.max_units,
            "units_sold": product.max_units,
            "market_price_start_qtr_aud": 2500.0,
            "current_value_total_aud": round(2500.0 * product.max_units, 2),
            "fair_value_per_unit_aud": float(response.fair_value_per_unit),
            "fair_value_total_aud": round(float(response.fair_value_per_unit) * product.max_units, 2),
            "spread_per_unit_aud": float(response.fair_value_per_unit) - 2500.0,
            "quarter_progress_pct": _quarter_progress_pct(product.relevant_quarter),
            "market_share_of_fair_pct": round((2500.0 / float(response.fair_value_per_unit) * 100.0), 1) if response.fair_value_per_unit else 0.0,
            "fair_premium_pct": round(((float(response.fair_value_per_unit) - 2500.0) / 2500.0 * 100.0), 1),
            "arbitrage_per_unit_aud": round(float(response.fair_value_per_unit) - 2500.0, 2),
            "arbitrage_total_aud": round((float(response.fair_value_per_unit) - 2500.0) * product.max_units, 2),
            "arbitrage_side": "LONG" if float(response.fair_value_per_unit) >= 2500.0 * 1.02 else ("SHORT" if float(response.fair_value_per_unit) <= 2500.0 * 0.98 else "NEUTRAL"),
            "recommendation": "BUY" if float(response.fair_value_per_unit) >= 2500.0 * 1.12 else ("HOLD" if float(response.fair_value_per_unit) >= 2500.0 * 1.04 else "WATCH"),
            "recommendation_reason": "Illustrative fallback example",
            "confidence_band_low_aud": float(response.confidence_band_low),
            "confidence_band_high_aud": float(response.confidence_band_high),
            "confidence_level": 0.8,
            "source_file": "example",
            "source_status": "fallback",
        }]

    for row in rows:
        if row.get("recommendation") == "HOLD":
            base_reason = str(row.get("recommendation_reason") or "")
            if "no new buy" not in base_reason.lower():
                row["recommendation_reason"] = f"{base_reason} · no new buy (hold existing only)".strip(" ·")

    collapse_directions = True
    if collapse_directions:
        grouped: dict[tuple[str, str, str, int], list[dict[str, object]]] = {}
        for row in rows:
            key = (
                str(row.get("contract_id", "")),
                str(row.get("quarter", "")),
                str(row.get("interconnector", "")),
                int(row.get("tranche_no", 0) or 0),
            )
            grouped.setdefault(key, []).append(row)

        collapsed_rows: list[dict[str, object]] = []
        for _, items in grouped.items():
            items_sorted = sorted(
                items,
                key=lambda item: abs(float(item.get("arbitrage_total_aud", 0.0) or 0.0)),
                reverse=True,
            )
            top = dict(items_sorted[0])
            directions = [
                f"{str(item.get('from_region', ''))}→{str(item.get('to_region', ''))}"
                for item in items_sorted
            ]
            top["direction_label"] = " | ".join(directions)
            top["from_region"] = "PAIR"
            top["to_region"] = "PAIR"
            top["legs"] = [
                {
                    "direction": f"{str(item.get('from_region', ''))}→{str(item.get('to_region', ''))}",
                    "market_price_start_qtr_aud": item.get("market_price_start_qtr_aud"),
                    "fair_value_per_unit_aud": item.get("fair_value_per_unit_aud"),
                    "arbitrage_per_unit_aud": item.get("arbitrage_per_unit_aud"),
                    "arbitrage_total_aud": item.get("arbitrage_total_aud"),
                    "arbitrage_side": item.get("arbitrage_side"),
                    "recommendation": item.get("recommendation"),
                }
                for item in items_sorted
            ]
            collapsed_rows.append(top)

        rows = sorted(
            collapsed_rows,
            key=lambda row: (
                str(row.get("quarter", "")),
                str(row.get("interconnector", "")),
                int(row.get("tranche_no", 0) or 0),
            ),
        )

    limited_rows = rows[:limit]
    return {
        "status": "ok",
        "path": str(RAW_SRA_RESULTS_DIR),
        "count": len(rows),
        "rows": limited_rows,
    }


@app.get("/ux/fair-value/dashboard")
def ux_fair_value_dashboard(
    quarterly_limit: int = Query(default=20, ge=1, le=500),
    diagnostics_limit: int = Query(default=20, ge=1, le=500),
    products_limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    summary = ux_fair_value_summary()
    quarterly = ux_fair_value_quarterly(limit=quarterly_limit)
    diagnostics = ux_fair_value_diagnostics(limit=diagnostics_limit)
    products = ux_fair_value_products(limit=products_limit)

    overall_status = "ok"
    if any(section.get("status") != "ok" for section in (summary, quarterly, diagnostics, products)):
        overall_status = "partial"

    return {
        "status": overall_status,
        "as_of": utc_now_iso(),
        "summary": summary,
        "products": products,
        "quarterly": quarterly,
        "diagnostics": diagnostics,
    }


@app.get("/ux/recommendations/monitoring")
def ux_recommendations_monitoring() -> dict:
    """Recommendation accuracy and alpha monitoring dashboard.
    
    Returns metrics for:
    - Hit rate by recommendation bucket (BUY/HOLD/AVOID/WATCH)
    - Calibration (confidence vs actual hit rate)
    - Average markout by bucket
    - Strategy performance vs baselines
    """
    hit_rates = recommendation_ledger.compute_hit_rate()
    markouts = recommendation_ledger.compute_average_markout()
    vs_baseline = recommendation_ledger.compute_vs_baseline()

    return {
        "status": "ok",
        "as_of": utc_now_iso(),
        "hit_rate_analysis": hit_rates,
        "average_markout": markouts,
        "vs_baseline_comparison": vs_baseline,
        "ledger_path": str(recommendation_ledger.ledger_path),
    }


@app.get("/ux/recommendations/by-product")
def ux_recommendations_by_product(
    product_id: str = Query(..., description="Product ID e.g. NSW1-QLD1"),
    quarter: str = Query(None, description="Optional quarter filter e.g. C2025Q3"),
) -> dict:
    """Retrieve all recommendations for a specific product.
    
    Args:
        product_id: Interconnector ID like NSW1-QLD1
        quarter: Optional quarter filter
        
    Returns:
        DataFrame of recommendations in JSON format.
    """
    recommendations = recommendation_ledger.get_recommendations_by_product(product_id, quarter)
    
    if recommendations.empty:
        return {
            "status": "ok",
            "message": f"No recommendations found for {product_id}",
            "count": 0,
            "records": [],
        }
    
    return {
        "status": "ok",
        "product_id": product_id,
        "quarter_filter": quarter,
        "count": len(recommendations),
        "records": recommendations.to_dict(orient="records"),
    }


@app.get("/ux/fair-value/fill-rate-model")
def ux_fill_rate_model_info() -> dict:
    """Information about the fill-rate-based fair value model.
    
    Explains:
    - Historical correlation (0.74) between fill rate and price
    - High-demand vs low-demand pricing averages
    - Recommendation thresholds and confidence scaling
    """
    return {
        "status": "ok",
        "model": "fill_rate_fair_value_v1",
        "description": "Fair value anchored to market price and tilted by demand intensity (fill rate)",
        "calibration": {
            "fill_rate_price_correlation": 0.74,
            "method": "market-relative adjustment",
            "fair_value_formula": "fair = market * (1 + 0.20*fill_signal + 0.05*volume_signal)",
            "fair_value_clamp": "[0.60x, 1.60x] of market price",
        },
        "recommendation_thresholds": {
            "note": "Thresholds scale with confidence: higher confidence = tighter thresholds",
            "buy_threshold_base": "12% below fair value (at low confidence)",
            "hold_threshold_base": "4% below fair value (at low confidence)",
            "avoid_threshold_base": "4% above fair value (at low confidence)",
        },
        "signals": {
            "fill_rate_signal": "[-1, 1] where 1=high demand, -1=low demand",
            "volume_signal": "[-1, 1] where 1=high liquidity, -1=low",
        },
    }


@app.get("/ux/market/correlations")
def ux_market_correlations() -> dict:
    frame = _load_market_frame_cached()
    result = correlation_summary(frame)
    return {
        "as_of": utc_now_iso(),
        **result,
    }


@app.get("/ux/market/trends")
def ux_market_trends() -> dict:
    frame = _load_market_frame_cached()
    result = trend_summary(frame)
    return {
        "as_of": utc_now_iso(),
        **result,
    }


@app.get("/ux/market/backtest")
def ux_market_backtest() -> dict:
    frame = _load_market_frame_cached()
    result = sequential_backtest_summary(frame)
    return {
        "as_of": utc_now_iso(),
        "method": "sequential_tranche_fill_rate_signal",
        **result,
    }


@app.get("/ux/market/arbitrage")
def ux_market_arbitrage(limit: int = Query(default=25, ge=1, le=200)) -> dict:
    rows = _load_product_mark_rows()
    if not rows:
        return {
            "status": "no_data",
            "as_of": utc_now_iso(),
            "count": 0,
            "gross_long_edge_aud": 0.0,
            "gross_short_edge_aud": 0.0,
            "gross_total_edge_aud": 0.0,
            "top_opportunities": [],
        }

    enriched = []
    for row in rows:
        arb_per_unit = float(row.get("arbitrage_per_unit_aud", row.get("spread_per_unit_aud", 0.0)) or 0.0)
        units_sold = int(row.get("units_sold", 0) or 0)
        arb_total = float(row.get("arbitrage_total_aud", round(arb_per_unit * units_sold, 2)) or 0.0)
        arb_side = row.get("arbitrage_side") or ("LONG" if arb_per_unit > 0 else ("SHORT" if arb_per_unit < 0 else "NEUTRAL"))

        enriched.append(
            {
                **row,
                "arbitrage_per_unit_aud": round(arb_per_unit, 2),
                "arbitrage_total_aud": round(arb_total, 2),
                "arbitrage_side": arb_side,
                "arbitrage_abs_total_aud": round(abs(arb_total), 2),
            }
        )

    gross_long = round(sum(item["arbitrage_total_aud"] for item in enriched if item["arbitrage_side"] == "LONG"), 2)
    gross_short = round(sum(abs(item["arbitrage_total_aud"]) for item in enriched if item["arbitrage_side"] == "SHORT"), 2)
    gross_total = round(gross_long + gross_short, 2)

    top = sorted(enriched, key=lambda x: float(x.get("arbitrage_abs_total_aud", 0.0)), reverse=True)[:limit]

    return {
        "status": "ok",
        "as_of": utc_now_iso(),
        "count": len(enriched),
        "gross_long_edge_aud": gross_long,
        "gross_short_edge_aud": gross_short,
        "gross_total_edge_aud": gross_total,
        "top_opportunities": top,
    }


@app.get("/ux/market/trade-candidates")
def ux_market_trade_candidates(
    limit: int = Query(default=20, ge=1, le=200),
    min_confidence: float = Query(default=0.35, ge=0.0, le=1.0),
    min_edge_pct: float = Query(default=2.0, ge=0.0, le=100.0),
    risk_budget_aud: float = Query(default=25000.0, gt=0.0, le=5_000_000.0),
    max_participation_pct: float = Query(default=10.0, ge=1.0, le=50.0),
) -> dict:
    rows = _load_product_mark_rows()
    if not rows:
        return {
            "status": "no_data",
            "as_of": utc_now_iso(),
            "count": 0,
            "candidates": [],
            "note": "No products available.",
        }

    candidates = _build_trade_candidates(
        rows=rows,
        min_confidence=min_confidence,
        min_edge_pct=min_edge_pct,
        risk_budget_aud=risk_budget_aud,
        max_participation_pct=max_participation_pct,
    )

    ranked = sorted(
        candidates,
        key=lambda item: (abs(float(item["expected_edge_aud"])), float(item["confidence"])),
        reverse=True,
    )[:limit]

    return {
        "status": "ok",
        "as_of": utc_now_iso(),
        "count": len(ranked),
        "filters": {
            "min_confidence": min_confidence,
            "min_edge_pct": min_edge_pct,
            "risk_budget_aud": risk_budget_aud,
            "max_participation_pct": max_participation_pct,
        },
        "candidates": ranked,
        "note": "Suggested spend is capped by risk budget and a liquidity participation limit to reduce market impact. Educational output only; not financial advice.",
    }


@app.get("/ux/market/best-buy-options")
def ux_market_best_buy_options(
    limit: int = Query(default=12, ge=1, le=200),
    min_confidence: float = Query(default=0.35, ge=0.0, le=1.0),
    min_edge_pct: float = Query(default=2.0, ge=0.0, le=100.0),
    risk_budget_aud: float = Query(default=25000.0, gt=0.0, le=5_000_000.0),
    max_participation_pct: float = Query(default=10.0, ge=1.0, le=50.0),
) -> dict:
    rows = _load_product_mark_rows()
    if not rows:
        return {
            "status": "no_data",
            "as_of": utc_now_iso(),
            "count": 0,
            "best_buys": [],
            "note": "No products available.",
        }

    candidates = _build_trade_candidates(
        rows=rows,
        min_confidence=min_confidence,
        min_edge_pct=min_edge_pct,
        risk_budget_aud=risk_budget_aud,
        max_participation_pct=max_participation_pct,
        side_filter={"LONG"},
    )

    ranked = sorted(
        candidates,
        key=lambda item: (
            float(item.get("expected_edge_per_dollar", 0.0) or 0.0),
            abs(float(item.get("expected_edge_aud", 0.0) or 0.0)),
            float(item.get("confidence", 0.0) or 0.0),
        ),
        reverse=True,
    )[:limit]

    quarter_summaries, year_summaries = _summarize_trade_groups(ranked)

    return {
        "status": "ok",
        "as_of": utc_now_iso(),
        "count": len(ranked),
        "filters": {
            "min_confidence": min_confidence,
            "min_edge_pct": min_edge_pct,
            "risk_budget_aud": risk_budget_aud,
            "max_participation_pct": max_participation_pct,
        },
        "best_buys": ranked,
        "quarter_summaries": quarter_summaries,
        "year_summaries": year_summaries,
        "note": "Buy-side shortlist ranked by edge per dollar, with max spend capped to reduce expected market impact. Educational output only; not financial advice.",
    }


@app.get("/ux/market/sell-quarter")
def ux_market_sell_quarter(
    min_confidence: float = Query(default=0.35, ge=0.0, le=1.0),
    min_edge_pct: float = Query(default=2.0, ge=0.0, le=100.0),
    risk_budget_aud: float = Query(default=25000.0, gt=0.0, le=5_000_000.0),
    max_participation_pct: float = Query(default=10.0, ge=1.0, le=50.0),
) -> dict:
    rows = _load_product_mark_rows()
    if not rows:
        return {
            "status": "no_data",
            "as_of": utc_now_iso(),
            "count": 0,
            "quarter_summaries": [],
            "year_summaries": [],
            "note": "No products available.",
        }

    sell_candidates = _build_trade_candidates(
        rows=rows,
        min_confidence=min_confidence,
        min_edge_pct=min_edge_pct,
        risk_budget_aud=risk_budget_aud,
        max_participation_pct=max_participation_pct,
        side_filter={"LONG", "SHORT"},
    )

    quarter_summaries, year_summaries = _summarize_trade_groups(sell_candidates)

    sell_rows = []
    for summary in quarter_summaries:
        sell_rows.append({
            **summary,
            "exit_price_aud": summary.get("sell_now_value_aud"),
            "projected_hold_pnl_aud": summary.get("total_projected_profit_aud"),
            "sell_entire_quarter_note": "Selling the entire quarter means exiting your full contract position now at the market value shown above. This is separate from the quarter's settlement payouts.",
            "sell_action": "SELL_ENTIRE_QUARTER",
        })

    return {
        "status": "ok",
        "as_of": utc_now_iso(),
        "count": len(sell_rows),
        "quarter_summaries": sell_rows,
        "year_summaries": year_summaries,
        "note": "Quarter exit view; use the exit price to decide whether to sell the full quarter position now or hold through settlement. Educational output only; not financial advice.",
    }

