from datetime import date, datetime

from src.transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher
from src.transmission_rights.services.aemo.sra_market_calendar import SRAMarketCalendar
from src.transmission_rights.services.aemo.sra_product_registry import SRAProductRegistry


SRA_RESULTS_SAMPLE = """C,NEM,SRRES,NEMMCO,PUBLIC,\"2026/06/15 14:23:45\"
I,RESIDUE_PUBLIC_DATA,,1,CONTRACTID,VERSIONNO,INTERCONNECTORID,FROMREGIONID,UNITSOFFERED,UNITSSOLD,CLEARINGPRICE,RESERVEPRICE
D,RESIDUE_PUBLIC_DATA,,1,C2029Q2T01,1,NSW1-QLD1,NSW1,62,62,1674.4,0
D,RESIDUE_PUBLIC_DATA,,1,C2029Q2T01,1,NSW1-QLD1,QLD1,108,108,22399.6,0
C,END OF REPORT,4
"""

AUCUNITS_SAMPLE = """C,NEM,AUCUNITS,AEMO,PUBLIC,2026/07/10,12:03:20
I,BILLING,AUCTION_UNITS,1,CONTRACTYEAR,WEEKNO,BILLRUNNO,STARTDATE,ENDDATE,BILLRUNTYPE,RESIDUEYEAR,QUARTER,INTERCONNECTORID,FROMREGIONID,PURCHASEDUNITS,TOTALSURPLUS,DISTRIBUTEDSURPLUS,AUCTIONFEES,NETPAYMENT,NETPAYMENTPERUNIT,ACCUMULATEDNETPAYMENT,ACCUMULATEDNETPAYMENTPERUNIT
D,BILLING,AUCTION_UNITS,1,2026,27,8,\"2026/06/28 00:00:00\",\"2026/07/04 00:00:00\",PRELIMINARY,2026,3,NSW1-QLD1,NSW1,562,772.30259230,904.13666933,-60.37494877,843.76172041,1.501355,843.76172041,1.501355
C,\"END OF REPORT\",3
"""


def test_parse_sra_results_rows() -> None:
    fetcher = HistoricalDataFetcher()
    snapshots = fetcher.parse_sra_results(SRA_RESULTS_SAMPLE)

    assert len(snapshots) == 2
    assert snapshots[0].contract_id == "C2029Q2T01"
    assert snapshots[0].quarter == "C2029Q2"
    assert snapshots[0].tranche_no == 1
    assert snapshots[0].directional_interconnector == "NSW1-QLD1"
    assert snapshots[1].from_region == "QLD1"


def test_load_registry_and_calendar_from_sra_results() -> None:
    fetcher = HistoricalDataFetcher()
    snapshots = fetcher.parse_sra_results(SRA_RESULTS_SAMPLE)

    registry = SRAProductRegistry()
    added = fetcher.load_products_from_sra_results(
        registry=registry,
        snapshots=snapshots,
        effective_date=date(2026, 6, 15),
    )
    assert added == 2

    products = registry.list_by_quarter("C2029Q2")
    assert len(products) == 2
    assert products[0].tranche_no == 1
    assert products[0].max_units > 0

    calendar = SRAMarketCalendar()
    added_events = fetcher.load_calendar_from_sra_results(
        calendar=calendar,
        snapshots=snapshots,
        auction_timestamp=datetime(2026, 6, 15, 14, 23, 45),
    )
    assert added_events == 1
    assert len(calendar.get_by_quarter("C2029Q2")) == 1


def test_fetch_product_definitions_snapshot_parses_rows(monkeypatch) -> None:
    fetcher = HistoricalDataFetcher()

    monkeypatch.setattr(
        fetcher,
        "list_auction_units_files",
        lambda: ["AUCUNITS_20260628.R008", "AUCUNITS_20260705.R001"],
    )
    monkeypatch.setattr(fetcher, "fetch_auction_units_file", lambda _: AUCUNITS_SAMPLE)

    snapshot = fetcher.fetch_product_definitions_snapshot("2026-07-01")
    assert snapshot is not None
    assert snapshot["source_file"] == "AUCUNITS_20260628.R008"
    assert snapshot["count"] == 1
    assert snapshot["rows"][0]["INTERCONNECTORID"] == "NSW1-QLD1"


def test_fetch_product_definitions_snapshot_prefers_latest_revision(monkeypatch) -> None:
    fetcher = HistoricalDataFetcher()

    monkeypatch.setattr(
        fetcher,
        "list_auction_units_files",
        lambda: [
            "AUCUNITS_20260628.R001",
            "AUCUNITS_20260628.R008",
            "AUCUNITS_20260705.R001",
        ],
    )
    monkeypatch.setattr(fetcher, "fetch_auction_units_file", lambda _: AUCUNITS_SAMPLE)

    snapshot = fetcher.fetch_product_definitions_snapshot("2026-06-30")
    assert snapshot is not None
    assert snapshot["source_file"] == "AUCUNITS_20260628.R008"


def test_fetch_sra_results_range_continues_after_file_error(monkeypatch) -> None:
    fetcher = HistoricalDataFetcher()

    monkeypatch.setattr(
        fetcher,
        "list_sra_results_files",
        lambda: [
            ("PUBLIC_SRRES_C2029Q2T01_20260615142345.csv", "C2029Q2", 1),
            ("PUBLIC_SRRES_C2029Q2T02_20260615142345.csv", "C2029Q2", 2),
        ],
    )

    def _fetch(name: str) -> str:
        if name.endswith("T01_20260615142345.csv"):
            raise RuntimeError("temporary fetch error")
        fetcher.cached_files[name] = SRA_RESULTS_SAMPLE.encode("utf-8")
        fetcher.metadata[name] = {"source": "SRA_Results"}
        return SRA_RESULTS_SAMPLE

    monkeypatch.setattr(fetcher, "fetch_sra_results_file", _fetch)

    fetched = fetcher.fetch_sra_results_range("C2029Q2", "C2029Q2")
    assert fetched == ["PUBLIC_SRRES_C2029Q2T02_20260615142345.csv"]