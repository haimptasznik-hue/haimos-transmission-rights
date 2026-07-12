from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from ..adapters.aemo.historical_data_fetcher import HistoricalDataFetcher
from ..domain.models import AllocationType, FairValueRequest, PortfolioPosition, SRAProduct, ValuationInputs
from .valuation import FairValueEngine


@dataclass(frozen=True)
class BacktestRow:
    filename: str
    quarter: str
    tranche_no: int
    interconnector_id: str
    from_region: str
    to_region: str
    units_offered: int
    units_sold: int
    clearing_price: float
    actual_residue_total: float
    actual_per_unit: float
    actual_total_payout: float
    model_per_unit: float
    model_total_payout: float
    pct_error_actual_per_unit: float
    pct_error_clearing_price: float


@dataclass(frozen=True)
class CalibrationResult:
    model_risk_discount: float
    liquidity_discount: float
    downside_multiplier: float
    upside_multiplier: float
    payout_error_weight: float
    clearing_price_error_weight: float
    ape_cap: Optional[float]
    quarter_balanced_weighting: bool
    n_rows: int
    mape_actual_per_unit: float
    mape_clearing_price: float
    weighted_score: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _percent_error(actual: float, predicted: float) -> float:
    if actual == 0:
        return 0.0 if predicted == 0 else 100.0
    return abs((predicted - actual) / actual) * 100.0


def _capped_error(error_value: float, ape_cap: Optional[float]) -> float:
    if ape_cap is None:
        return error_value
    return min(error_value, ape_cap)


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.0
    denominator = sum(weights)
    if denominator <= 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights, strict=False)) / denominator


def _other_region(interconnector_id: str, from_region: str) -> str:
    if "-" not in interconnector_id:
        return ""
    left, right = interconnector_id.split("-", 1)
    if from_region == left:
        return right
    if from_region == right:
        return left
    return ""


def _build_domain_product(
    interconnector_id: str,
    from_region: str,
    quarter: str,
    tranche_no: int,
    units_offered: int,
) -> SRAProduct:
    return SRAProduct(
        interconnector_id=interconnector_id,
        direction_from_region=from_region,
        direction_to_region=_other_region(interconnector_id, from_region),
        unit_category_id=f"{interconnector_id}/{from_region}",
        relevant_quarter=quarter,
        tranche_no=tranche_no,
        allocation_type=AllocationType.PRIMARY,
        max_units=max(int(units_offered), 1),
        unit_proportion=1 / max(int(units_offered), 1),
    )


def load_backtest_rows(
    results_dir: Path,
    dispatch_quarterly_csv: Path,
) -> pd.DataFrame:
    """
    Build a row-level backtest frame from historical SRA_Results and reconstructed IRSR.

    Each row is a single tranche / directional region from the AEMO result files.
    The actual settlement payout per unit is derived from the reconstructed quarterly
    Dispatch_IRSR totals divided by total units sold for that quarter / interconnector / region.
    """
    fetcher = HistoricalDataFetcher()
    dispatch_df = pd.read_csv(dispatch_quarterly_csv)
    if dispatch_df.empty:
        return pd.DataFrame()

    dispatch_lookup = dispatch_df.set_index(["quarter", "interconnector_id", "from_region"])["residue_aud"]

    raw_rows: list[dict[str, object]] = []
    for path in sorted(results_dir.glob("*.csv")):
        csv_text = path.read_text(encoding="utf-8")
        snapshots = fetcher.parse_sra_results(csv_text)
        for snapshot in snapshots:
            raw_rows.append(
                {
                    "filename": path.name,
                    "quarter": snapshot.quarter,
                    "tranche_no": snapshot.tranche_no,
                    "interconnector_id": snapshot.directional_interconnector,
                    "from_region": snapshot.from_region,
                    "to_region": _other_region(snapshot.directional_interconnector, snapshot.from_region),
                    "units_offered": snapshot.units_offered,
                    "units_sold": snapshot.units_sold,
                    "clearing_price": float(snapshot.clearing_price),
                }
            )

    if not raw_rows:
        return pd.DataFrame()

    raw_df = pd.DataFrame(raw_rows)
    sold_totals = (
        raw_df.groupby(["quarter", "interconnector_id", "from_region"], as_index=False)["units_sold"]
        .sum()
        .rename(columns={"units_sold": "total_units_sold"})
    )
    merged = raw_df.merge(sold_totals, on=["quarter", "interconnector_id", "from_region"], how="left")

    actual_residue_totals: list[float] = []
    actual_per_units: list[float] = []
    actual_total_payouts: list[float] = []
    for _, row in merged.iterrows():
        key = (row["quarter"], row["interconnector_id"], row["from_region"])
        if key not in dispatch_lookup.index:
            actual_residue_totals.append(float("nan"))
            actual_per_units.append(float("nan"))
            actual_total_payouts.append(float("nan"))
            continue
        residue_total = float(dispatch_lookup.loc[key])
        total_units_sold = float(row["total_units_sold"])
        if total_units_sold <= 0:
            actual_per_unit = 0.0
        else:
            actual_per_unit = residue_total / total_units_sold
        actual_residue_totals.append(residue_total)
        actual_per_units.append(actual_per_unit)
        actual_total_payouts.append(actual_per_unit * float(row["units_sold"]))

    merged["actual_residue_total"] = actual_residue_totals
    merged["actual_per_unit"] = actual_per_units
    merged["actual_total_payout"] = actual_total_payouts
    merged = merged.dropna(subset=["actual_residue_total", "actual_per_unit"]).reset_index(drop=True)
    return merged


def score_calibration(
    backtest_df: pd.DataFrame,
    model_risk_discount: float,
    liquidity_discount: float,
    downside_multiplier: float = 0.8,
    upside_multiplier: float = 1.2,
    payout_error_weight: float = 0.7,
    clearing_price_error_weight: float = 0.3,
    ape_cap: Optional[float] = None,
    quarter_balanced_weighting: bool = False,
    min_total_discount: float = 0.0,
    discount_penalty_strength: float = 100.0,
) -> CalibrationResult:
    total_weight = payout_error_weight + clearing_price_error_weight
    if total_weight <= 0:
        payout_weight = 0.5
        price_weight = 0.5
    else:
        payout_weight = payout_error_weight / total_weight
        price_weight = clearing_price_error_weight / total_weight

    if backtest_df.empty:
        return CalibrationResult(
            model_risk_discount=model_risk_discount,
            liquidity_discount=liquidity_discount,
            downside_multiplier=downside_multiplier,
            upside_multiplier=upside_multiplier,
            payout_error_weight=payout_weight,
            clearing_price_error_weight=price_weight,
            ape_cap=ape_cap,
            quarter_balanced_weighting=quarter_balanced_weighting,
            n_rows=0,
            mape_actual_per_unit=0.0,
            mape_clearing_price=0.0,
            weighted_score=0.0,
        )

    engine = FairValueEngine()
    actual_errors: list[float] = []
    price_errors: list[float] = []
    row_weights: list[float] = []

    quarter_sizes: dict[str, int] = {}
    if quarter_balanced_weighting:
        quarter_sizes = backtest_df["quarter"].value_counts().to_dict()

    for _, row in backtest_df.iterrows():
        product = _build_domain_product(
            interconnector_id=str(row["interconnector_id"]),
            from_region=str(row["from_region"]),
            quarter=str(row["quarter"]),
            tranche_no=int(row["tranche_no"]),
            units_offered=int(row["units_offered"]),
        )
        position = PortfolioPosition(
            units_held=int(row["units_sold"]),
            acquisition_price_per_unit=float(row["clearing_price"]),
        )
        expected_irsr = float(row["actual_residue_total"]) * product.max_units / max(float(row["total_units_sold"]), 1.0)
        inputs = ValuationInputs(
            expected_irsr=expected_irsr,
            downside_irsr=expected_irsr * downside_multiplier,
            upside_irsr=expected_irsr * upside_multiplier,
            model_risk_discount=model_risk_discount,
            liquidity_discount=liquidity_discount,
        )
        request = FairValueRequest(product=product, position=position, inputs=inputs)
        response = engine.value(request)

        actual_per_unit = float(row["actual_per_unit"])
        clearing_price = float(row["clearing_price"])
        actual_errors.append(
            _capped_error(_percent_error(actual_per_unit, response.fair_value_per_unit), ape_cap)
        )
        price_errors.append(
            _capped_error(_percent_error(clearing_price, response.fair_value_per_unit), ape_cap)
        )
        if quarter_balanced_weighting:
            quarter_key = str(row["quarter"])
            q_size = quarter_sizes.get(quarter_key, 1)
            row_weights.append(1 / max(q_size, 1))
        else:
            row_weights.append(1.0)

    mape_actual = _weighted_mean(actual_errors, row_weights)
    mape_price = _weighted_mean(price_errors, row_weights)
    base_score = (payout_weight * mape_actual) + (price_weight * mape_price)
    total_discount = model_risk_discount + liquidity_discount
    discount_shortfall = max(0.0, min_total_discount - total_discount)
    weighted_score = base_score + (discount_shortfall * discount_penalty_strength)

    return CalibrationResult(
        model_risk_discount=model_risk_discount,
        liquidity_discount=liquidity_discount,
        downside_multiplier=downside_multiplier,
        upside_multiplier=upside_multiplier,
        payout_error_weight=payout_weight,
        clearing_price_error_weight=price_weight,
        ape_cap=ape_cap,
        quarter_balanced_weighting=quarter_balanced_weighting,
        n_rows=len(backtest_df),
        mape_actual_per_unit=mape_actual,
        mape_clearing_price=mape_price,
        weighted_score=weighted_score,
    )


def grid_search_calibration(
    backtest_df: pd.DataFrame,
    model_risk_discounts: Iterable[float],
    liquidity_discounts: Iterable[float],
    downside_multiplier: float = 0.8,
    upside_multiplier: float = 1.2,
    payout_error_weight: float = 0.7,
    clearing_price_error_weight: float = 0.3,
    ape_cap: Optional[float] = None,
    quarter_balanced_weighting: bool = False,
    min_total_discount: float = 0.0,
    discount_penalty_strength: float = 100.0,
) -> CalibrationResult:
    best: Optional[CalibrationResult] = None
    for model_risk_discount in model_risk_discounts:
        for liquidity_discount in liquidity_discounts:
            result = score_calibration(
                backtest_df=backtest_df,
                model_risk_discount=model_risk_discount,
                liquidity_discount=liquidity_discount,
                downside_multiplier=downside_multiplier,
                upside_multiplier=upside_multiplier,
                payout_error_weight=payout_error_weight,
                clearing_price_error_weight=clearing_price_error_weight,
                ape_cap=ape_cap,
                quarter_balanced_weighting=quarter_balanced_weighting,
                min_total_discount=min_total_discount,
                discount_penalty_strength=discount_penalty_strength,
            )
            if best is None or result.weighted_score < best.weighted_score:
                best = result
    if best is None:
        total_weight = payout_error_weight + clearing_price_error_weight
        if total_weight <= 0:
            payout_weight = 0.5
            price_weight = 0.5
        else:
            payout_weight = payout_error_weight / total_weight
            price_weight = clearing_price_error_weight / total_weight
        return CalibrationResult(
            0.0,
            0.0,
            downside_multiplier,
            upside_multiplier,
            payout_weight,
            price_weight,
            ape_cap,
            quarter_balanced_weighting,
            0,
            0.0,
            0.0,
            0.0,
        )
    return best


def calibration_grid_scores(
    backtest_df: pd.DataFrame,
    model_risk_discounts: Iterable[float],
    liquidity_discounts: Iterable[float],
    downside_multiplier: float = 0.8,
    upside_multiplier: float = 1.2,
    payout_error_weight: float = 0.7,
    clearing_price_error_weight: float = 0.3,
    ape_cap: Optional[float] = None,
    quarter_balanced_weighting: bool = False,
    min_total_discount: float = 0.0,
    discount_penalty_strength: float = 100.0,
) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for model_risk_discount in model_risk_discounts:
        for liquidity_discount in liquidity_discounts:
            result = score_calibration(
                backtest_df=backtest_df,
                model_risk_discount=model_risk_discount,
                liquidity_discount=liquidity_discount,
                downside_multiplier=downside_multiplier,
                upside_multiplier=upside_multiplier,
                payout_error_weight=payout_error_weight,
                clearing_price_error_weight=clearing_price_error_weight,
                ape_cap=ape_cap,
                quarter_balanced_weighting=quarter_balanced_weighting,
                min_total_discount=min_total_discount,
                discount_penalty_strength=discount_penalty_strength,
            )
            total_discount = model_risk_discount + liquidity_discount
            rows.append(
                {
                    "model_risk_discount": model_risk_discount,
                    "liquidity_discount": liquidity_discount,
                    "total_discount": total_discount,
                    "discount_shortfall": max(0.0, min_total_discount - total_discount),
                    "mape_actual_per_unit": result.mape_actual_per_unit,
                    "mape_clearing_price": result.mape_clearing_price,
                    "weighted_score": result.weighted_score,
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("weighted_score").reset_index(drop=True)


def backtest_with_calibration(
    results_dir: Path,
    dispatch_quarterly_csv: Path,
    model_risk_discounts: Iterable[float],
    liquidity_discounts: Iterable[float],
    downside_multiplier: float = 0.8,
    upside_multiplier: float = 1.2,
    payout_error_weight: float = 0.7,
    clearing_price_error_weight: float = 0.3,
    ape_cap: Optional[float] = None,
    quarter_balanced_weighting: bool = False,
    min_total_discount: float = 0.0,
    discount_penalty_strength: float = 100.0,
) -> tuple[pd.DataFrame, CalibrationResult]:
    backtest_df = load_backtest_rows(results_dir, dispatch_quarterly_csv)
    if backtest_df.empty:
        total_weight = payout_error_weight + clearing_price_error_weight
        if total_weight <= 0:
            payout_weight = 0.5
            price_weight = 0.5
        else:
            payout_weight = payout_error_weight / total_weight
            price_weight = clearing_price_error_weight / total_weight
        return backtest_df, CalibrationResult(
            0.0,
            0.0,
            downside_multiplier,
            upside_multiplier,
            payout_weight,
            price_weight,
            ape_cap,
            quarter_balanced_weighting,
            0,
            0.0,
            0.0,
            0.0,
        )
    calibration = grid_search_calibration(
        backtest_df=backtest_df,
        model_risk_discounts=model_risk_discounts,
        liquidity_discounts=liquidity_discounts,
        downside_multiplier=downside_multiplier,
        upside_multiplier=upside_multiplier,
        payout_error_weight=payout_error_weight,
        clearing_price_error_weight=clearing_price_error_weight,
        ape_cap=ape_cap,
        quarter_balanced_weighting=quarter_balanced_weighting,
        min_total_discount=min_total_discount,
        discount_penalty_strength=discount_penalty_strength,
    )

    result_df = _apply_calibration_to_rows(backtest_df, calibration, ape_cap=ape_cap)
    return result_df, calibration


def _apply_calibration_to_rows(
    backtest_df: pd.DataFrame,
    calibration: CalibrationResult,
    ape_cap: Optional[float] = None,
) -> pd.DataFrame:
    if backtest_df.empty:
        return backtest_df.copy()

    engine = FairValueEngine()
    model_per_units: list[float] = []
    model_totals: list[float] = []
    pct_error_actual_per_units: list[float] = []
    pct_error_clearing_prices: list[float] = []

    for _, row in backtest_df.iterrows():
        product = _build_domain_product(
            interconnector_id=str(row["interconnector_id"]),
            from_region=str(row["from_region"]),
            quarter=str(row["quarter"]),
            tranche_no=int(row["tranche_no"]),
            units_offered=int(row["units_offered"]),
        )
        position = PortfolioPosition(
            units_held=int(row["units_sold"]),
            acquisition_price_per_unit=float(row["clearing_price"]),
        )
        expected_irsr = float(row["actual_residue_total"]) * product.max_units / max(float(row["total_units_sold"]), 1.0)
        inputs = ValuationInputs(
            expected_irsr=expected_irsr,
            downside_irsr=expected_irsr * calibration.downside_multiplier,
            upside_irsr=expected_irsr * calibration.upside_multiplier,
            model_risk_discount=calibration.model_risk_discount,
            liquidity_discount=calibration.liquidity_discount,
        )
        request = FairValueRequest(product=product, position=position, inputs=inputs)
        response = engine.value(request)

        model_per_units.append(float(response.fair_value_per_unit))
        model_totals.append(float(response.fair_value_total))
        pct_error_actual_per_units.append(
            _capped_error(
                _percent_error(float(row["actual_per_unit"]), float(response.fair_value_per_unit)),
                ape_cap,
            )
        )
        pct_error_clearing_prices.append(
            _capped_error(
                _percent_error(float(row["clearing_price"]), float(response.fair_value_per_unit)),
                ape_cap,
            )
        )

    result_df = backtest_df.copy()
    result_df["model_per_unit"] = model_per_units
    result_df["model_total_payout"] = model_totals
    result_df["pct_error_actual_per_unit"] = pct_error_actual_per_units
    result_df["pct_error_clearing_price"] = pct_error_clearing_prices
    return result_df


def backtest_with_quarter_calibration(
    results_dir: Path,
    dispatch_quarterly_csv: Path,
    model_risk_discounts: Iterable[float],
    liquidity_discounts: Iterable[float],
    downside_multiplier: float = 0.8,
    upside_multiplier: float = 1.2,
    payout_error_weight: float = 0.7,
    clearing_price_error_weight: float = 0.3,
    ape_cap: Optional[float] = None,
    quarter_balanced_weighting: bool = False,
    min_total_discount: float = 0.0,
    discount_penalty_strength: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    backtest_df = load_backtest_rows(results_dir, dispatch_quarterly_csv)
    if backtest_df.empty:
        return backtest_df, pd.DataFrame()

    evaluated_frames: list[pd.DataFrame] = []
    calibration_rows: list[dict[str, float | str | int]] = []

    for quarter, quarter_df in backtest_df.groupby("quarter", as_index=False):
        calibration = grid_search_calibration(
            backtest_df=quarter_df,
            model_risk_discounts=model_risk_discounts,
            liquidity_discounts=liquidity_discounts,
            downside_multiplier=downside_multiplier,
            upside_multiplier=upside_multiplier,
            payout_error_weight=payout_error_weight,
            clearing_price_error_weight=clearing_price_error_weight,
            ape_cap=ape_cap,
            quarter_balanced_weighting=quarter_balanced_weighting,
            min_total_discount=min_total_discount,
            discount_penalty_strength=discount_penalty_strength,
        )
        evaluated = _apply_calibration_to_rows(quarter_df, calibration, ape_cap=ape_cap)
        evaluated["calibrated_model_risk_discount"] = calibration.model_risk_discount
        evaluated["calibrated_liquidity_discount"] = calibration.liquidity_discount
        evaluated_frames.append(evaluated)
        calibration_rows.append(
            {
                "quarter": str(quarter),
                "rows": int(len(quarter_df)),
                "model_risk_discount": calibration.model_risk_discount,
                "liquidity_discount": calibration.liquidity_discount,
                "payout_error_weight": calibration.payout_error_weight,
                "clearing_price_error_weight": calibration.clearing_price_error_weight,
                "ape_cap": calibration.ape_cap if calibration.ape_cap is not None else -1.0,
                "quarter_balanced_weighting": int(calibration.quarter_balanced_weighting),
                "mape_actual_per_unit": calibration.mape_actual_per_unit,
                "mape_clearing_price": calibration.mape_clearing_price,
                "weighted_score": calibration.weighted_score,
            }
        )

    combined = pd.concat(evaluated_frames, ignore_index=True).sort_values(
        ["quarter", "interconnector_id", "from_region", "tranche_no", "filename"]
    )
    calibration_df = pd.DataFrame(calibration_rows).sort_values("quarter")
    return combined, calibration_df


def summarize_by_quarter(backtest_df: pd.DataFrame) -> pd.DataFrame:
    if backtest_df.empty:
        return pd.DataFrame()
    return (
        backtest_df.groupby("quarter", as_index=False)
        .agg(
            rows=("filename", "count"),
            actual_per_unit_mape=("pct_error_actual_per_unit", "mean"),
            clearing_price_mape=("pct_error_clearing_price", "mean"),
            actual_total_payout=("actual_total_payout", "sum"),
            model_total_payout=("model_total_payout", "sum"),
        )
        .sort_values("quarter")
    )
