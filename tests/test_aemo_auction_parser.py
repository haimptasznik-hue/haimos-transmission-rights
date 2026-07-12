from decimal import Decimal

from src.transmission_rights.services.aemo.sra_auction_parser import SRAAuctionParser

SRA_RESULTS_SAMPLE = """C,NEM,SRRES,NEMMCO,PUBLIC,\"2026/07/01 10:50:46\"
C,\"SETTLEMENTS RESIDUE CONTRACT REPORT\",\"For Contract ID C2027Q3T01, VersionNo 5\",C2027Q3T01,5
I,RESIDUE_PUBLIC_DATA,,1,CONTRACTID,VERSIONNO,INTERCONNECTORID,FROMREGIONID,UNITSOFFERED,UNITSSOLD,CLEARINGPRICE,RESERVEPRICE
D,RESIDUE_PUBLIC_DATA,,1,C2027Q3T01,5,NSW1-QLD1,NSW1,62,62,3503,0
D,RESIDUE_PUBLIC_DATA,,1,C2027Q3T01,5,NSW1-QLD1,QLD1,108,108,30912,0
C,END OF REPORT,5
"""


def test_ingest_sra_results_csv_text_registers_unique_rows() -> None:
    parser = SRAAuctionParser()

    ingested = parser.ingest_sra_results_csv_text(SRA_RESULTS_SAMPLE)

    assert ingested == 2
    assert len(parser.auction_results) == 2
    assert parser.auction_results[0].auction_datetime == "2026-07-01T10:50:46"
    assert parser.auction_results[0].status == "cleared"
    assert parser.get_units_sold("NSW1-QLD1", "C2027Q3") == 170
    assert parser.get_units_offered("NSW1-QLD1", "C2027Q3") == 170
    assert parser.get_clearing_price("NSW1-QLD1", "C2027Q3", 1) == Decimal("30912")


def test_ingest_sra_results_csv_text_deduplicates_repeated_payload() -> None:
    parser = SRAAuctionParser()

    parser.ingest_sra_results_csv_text(SRA_RESULTS_SAMPLE)
    parser.ingest_sra_results_csv_text(SRA_RESULTS_SAMPLE)

    assert len(parser.auction_results) == 2
    assert parser.get_units_sold("NSW1-QLD1", "C2027Q3") == 170
