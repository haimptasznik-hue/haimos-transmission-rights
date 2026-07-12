import json

from fastapi.testclient import TestClient

from transmission_rights.api import main as api_main


client = TestClient(api_main.app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload


def test_ux_summary_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main, "FAIR_VALUE_OUTPUT_DIR", tmp_path)

    response = client.get("/ux/fair-value/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "missing"


def test_ux_summary_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main, "FAIR_VALUE_OUTPUT_DIR", tmp_path)

    summary = {
        "calibration_scope": "global",
        "weighted_score": 64.2,
    }
    (tmp_path / "fair_value_calibration_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )

    response = client.get("/ux/fair-value/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["calibration_scope"] == "global"


def test_ux_quarterly_and_diagnostics_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main, "FAIR_VALUE_OUTPUT_DIR", tmp_path)

    (tmp_path / "fair_value_backtest_by_quarter.csv").write_text(
        "quarter,mape_actual_per_unit\nC2025Q3,10.0\nC2025Q4,9.5\n",
        encoding="utf-8",
    )
    (tmp_path / "fair_value_calibration_diagnostics.csv").write_text(
        "quarter,model_risk_discount,weighted_score\nC2025Q3,0.05,74.0\nC2025Q3,0.10,75.0\n",
        encoding="utf-8",
    )

    quarterly_response = client.get("/ux/fair-value/quarterly?limit=1")
    assert quarterly_response.status_code == 200
    quarterly_payload = quarterly_response.json()
    assert quarterly_payload["status"] == "ok"
    assert quarterly_payload["count"] == 1
    assert quarterly_payload["rows"][0]["quarter"] == "C2025Q3"

    diagnostics_response = client.get("/ux/fair-value/diagnostics?limit=1")
    assert diagnostics_response.status_code == 200
    diagnostics_payload = diagnostics_response.json()
    assert diagnostics_payload["status"] == "ok"
    assert diagnostics_payload["count"] == 1
    assert diagnostics_payload["rows"][0]["model_risk_discount"] == "0.05"


def test_ux_dashboard_partial_when_files_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main, "FAIR_VALUE_OUTPUT_DIR", tmp_path)

    response = client.get("/ux/fair-value/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["summary"]["status"] == "missing"
    assert payload["quarterly"]["status"] == "missing"
    assert payload["diagnostics"]["status"] == "missing"


def test_ux_dashboard_ok_with_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_main, "FAIR_VALUE_OUTPUT_DIR", tmp_path)

    (tmp_path / "fair_value_calibration_summary.json").write_text(
        json.dumps({"calibration_scope": "quarter", "weighted_score_mean": 64.9}),
        encoding="utf-8",
    )
    (tmp_path / "fair_value_backtest_by_quarter.csv").write_text(
        "quarter,mape_actual_per_unit\nC2025Q3,10.0\nC2025Q4,9.5\n",
        encoding="utf-8",
    )
    (tmp_path / "fair_value_calibration_diagnostics.csv").write_text(
        "quarter,model_risk_discount,weighted_score\nC2025Q3,0.05,74.0\nC2025Q3,0.10,75.0\n",
        encoding="utf-8",
    )

    response = client.get("/ux/fair-value/dashboard?quarterly_limit=1&diagnostics_limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["summary"]["calibration_scope"] == "quarter"
    assert payload["quarterly"]["count"] == 1
    assert payload["diagnostics"]["count"] == 1
