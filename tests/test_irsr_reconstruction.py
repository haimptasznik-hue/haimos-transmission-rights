import io
import zipfile
from decimal import Decimal

import pandas as pd

from src.transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher


def _build_dispatch_zip(csv_content: str) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sample.csv", csv_content)
    return payload.getvalue()


def test_parse_dispatch_irsr_zip_bytes() -> None:
    csv_data = "\n".join(
        [
            "C,NEMP.WORLD,DISPATCH_IRSR,AEMO,PUBLIC,2026/07/11,13:11:11",
            "I,DISPATCH,IRSR,2,TRADING_INTERVAL,INTERCONNECTORID,FROMREGIONID,RESIDUE",
            'D,DISPATCH,IRSR,2,"2026/07/11 13:15:00",NSW1-QLD1,NSW1,0',
            'D,DISPATCH,IRSR,2,"2026/07/11 13:15:00",NSW1-QLD1,QLD1,717.833410',
            "C,END OF REPORT,4",
        ]
    )
    content = _build_dispatch_zip(csv_data)
    records = HistoricalDataFetcher.parse_dispatch_irsr_zip_bytes(content)

    assert len(records) == 2
    assert records[0].interconnector_id == "NSW1-QLD1"
    assert records[1].from_region == "QLD1"
    assert records[1].residue_aud == Decimal("717.833410")


def test_quarter_from_dispatch_filename_patterns() -> None:
    assert (
        HistoricalDataFetcher._quarter_from_dispatch_filename(
            "PUBLIC_DISPATCH_IRSR_202607111315_0000000526907351.zip"
        )
        == "C2026Q3"
    )
    assert (
        HistoricalDataFetcher._quarter_from_dispatch_filename("PUBLIC_DISPATCH_IRSR_20250701.zip")
        == "C2025Q3"
    )


def test_reconstruct_irsr_quarterly() -> None:
    csv_data = "\n".join(
        [
            "I,DISPATCH,IRSR,2,TRADING_INTERVAL,INTERCONNECTORID,FROMREGIONID,RESIDUE",
            'D,DISPATCH,IRSR,2,"2026/07/11 13:15:00",NSW1-QLD1,NSW1,100',
            'D,DISPATCH,IRSR,2,"2026/07/11 13:15:00",NSW1-QLD1,QLD1,200',
            'D,DISPATCH,IRSR,2,"2026/07/12 13:15:00",NSW1-QLD1,NSW1,50',
        ]
    )
    content = _build_dispatch_zip(csv_data)
    fetcher = HistoricalDataFetcher()
    filename = "PUBLIC_DISPATCH_IRSR_202607111315_0000000000000001.zip"
    fetcher.cached_files[filename] = content

    df = fetcher.reconstruct_irsr_quarterly([filename])

    assert len(df) == 2
    nsw_row = df[(df["interconnector_id"] == "NSW1-QLD1") & (df["from_region"] == "NSW1")].iloc[0]
    qld_row = df[(df["interconnector_id"] == "NSW1-QLD1") & (df["from_region"] == "QLD1")].iloc[0]
    assert nsw_row["quarter"] == "C2026Q3"
    assert float(nsw_row["residue_aud"]) == 150.0
    assert float(qld_row["residue_aud"]) == 200.0


def test_reconstruct_irsr_quarterly_averages_within_trading_interval() -> None:
    csv_data = "\n".join(
        [
            "I,DISPATCH,IRSR,2,TRADING_INTERVAL,INTERCONNECTORID,FROMREGIONID,RESIDUE",
            'D,DISPATCH,IRSR,2,"2026/07/11 13:05:00",NSW1-QLD1,NSW1,100',
            'D,DISPATCH,IRSR,2,"2026/07/11 13:10:00",NSW1-QLD1,NSW1,200',
            'D,DISPATCH,IRSR,2,"2026/07/11 13:35:00",NSW1-QLD1,NSW1,50',
        ]
    )
    content = _build_dispatch_zip(csv_data)
    fetcher = HistoricalDataFetcher()
    filename = "PUBLIC_DISPATCH_IRSR_202607111315_0000000000000002.zip"
    fetcher.cached_files[filename] = content

    df = fetcher.reconstruct_irsr_quarterly([filename])

    assert len(df) == 1
    row = df.iloc[0]
    assert row["quarter"] == "C2026Q3"
    assert row["interconnector_id"] == "NSW1-QLD1"
    assert row["from_region"] == "NSW1"
    assert float(row["residue_aud"]) == 200.0


def test_reconcile_dispatch_vs_auction_units() -> None:
    fetcher = HistoricalDataFetcher()
    dispatch_df = pd.DataFrame(
        [
            {
                "quarter": "C2026Q3",
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "residue_aud": 100.0,
            }
        ]
    )
    auction_df = pd.DataFrame(
        [
            {
                "QUARTER": "3",
                "INTERCONNECTORID": "NSW1-QLD1",
                "FROMREGIONID": "NSW1",
                "NETPAYMENT": "90",
            }
        ]
    )

    reconciled = fetcher.reconcile_dispatch_vs_auction_units(dispatch_df, auction_df, "C2026Q3")

    assert len(reconciled) == 1
    row = reconciled.iloc[0]
    assert float(row["dispatch_residue_aud"]) == 100.0
    assert float(row["auction_netpayment_aud"]) == 90.0
    assert float(row["delta_aud"]) == 10.0