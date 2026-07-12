#!/usr/bin/env python3
"""
Build SRA payout history: join SETIRSURPLUS (ground-truth surplus $)
with RESIDUE_PUBLIC_DATA (units_sold + clearing_price) to produce:

  payout_per_unit = total_surplus_aud / total_units_sold
  alpha           = payout_per_unit - weighted_avg_clearing_price

Output: data/derived/sra/sra_payout_history.csv

Columns:
  quarter, interconnector_id, from_region,
  total_surplus_aud,          # from SETIRSURPLUS (AEMO ground-truth)
  total_units_sold,           # sum of units_sold across all tranches (RESIDUE_PUBLIC_DATA)
  payout_per_unit,            # surplus / units
  weighted_avg_clearing_price,# sum(units_sold * clearing_price) / total_units_sold
  alpha,                      # payout_per_unit - weighted_avg_clearing_price
  alpha_pct                   # alpha / weighted_avg_clearing_price * 100
"""

from pathlib import Path
import pandas as pd

SETIRSURPLUS = Path("data/derived/irsr/setirsurplus_quarterly_closed.csv")
AUCTION_RESULTS = Path("data/derived/sra/sra_auction_results.csv")
OUT = Path("data/derived/sra/sra_payout_history.csv")

OUT.parent.mkdir(parents=True, exist_ok=True)


def main():
    surplus = pd.read_csv(SETIRSURPLUS)
    auction = pd.read_csv(AUCTION_RESULTS)

    # --- Aggregate auction results to quarter level ---
    # total_units_sold = sum(units_sold) across all tranches
    # weighted_avg_clearing_price = sum(units_sold * clearing_price) / total_units_sold
    auction["value_sold"] = auction["units_sold"] * auction["clearing_price"]

    agg = auction.groupby(["quarter", "interconnector_id", "from_region"]).agg(
        total_units_sold=("units_sold", "sum"),
        total_value_sold=("value_sold", "sum"),
    ).reset_index()

    agg["weighted_avg_clearing_price"] = (
        agg["total_value_sold"] / agg["total_units_sold"]
    ).round(4)

    # --- Join with SETIRSURPLUS ---
    # Normalise interconnector names: SETIRSURPLUS uses interconnector_id column
    merged = surplus.merge(
        agg,
        left_on=["quarter", "interconnector_id", "from_region"],
        right_on=["quarter", "interconnector_id", "from_region"],
        how="left",
    )

    # Drop rows with no auction data (shouldn't happen for closed quarters, but be safe)
    n_before = len(merged)
    merged = merged.dropna(subset=["total_units_sold"])
    if len(merged) < n_before:
        print(f"  WARNING: dropped {n_before - len(merged)} rows with no auction data")

    # --- Compute payout per unit and alpha ---
    merged["payout_per_unit"] = (
        merged["surplus_aud"] / merged["total_units_sold"]
    ).round(4)

    merged["alpha"] = (
        merged["payout_per_unit"] - merged["weighted_avg_clearing_price"]
    ).round(4)

    merged["alpha_pct"] = (
        merged["alpha"] / merged["weighted_avg_clearing_price"] * 100
    ).round(2)

    # Clean up column order
    out = merged[[
        "quarter", "interconnector_id", "from_region",
        "surplus_aud", "total_units_sold",
        "payout_per_unit", "weighted_avg_clearing_price",
        "alpha", "alpha_pct",
    ]].sort_values(["quarter", "interconnector_id", "from_region"])

    out.to_csv(OUT, index=False)

    # --- Summary ---
    print(f"Rows written: {len(out)}")
    print(f"Quarters:     {sorted(out['quarter'].unique())}")
    print(f"Output:       {OUT}")
    print()
    print("Alpha summary by category (mean across all closed quarters):")
    summary = (
        out.groupby(["interconnector_id", "from_region"])[["alpha_pct"]]
        .agg(["mean", "std", "min", "max"])
        .round(1)
    )
    summary.columns = ["mean_%", "std_%", "min_%", "max_%"]
    print(summary.to_string())
    print()
    print("Sample rows (C2025Q3):")
    print(out[out["quarter"] == "C2025Q3"].to_string(index=False))


if __name__ == "__main__":
    main()
