from transmission_rights.adapters.aemo_feeds import list_dispatch_irsr_files, list_sra_results_files


def test_dispatch_irsr_files_discoverable() -> None:
    """Verify we can list live DISPATCH_IRSR files from NEMWeb."""
    files = list_dispatch_irsr_files(limit=5)
    assert len(files) > 0, "Should find at least one DISPATCH_IRSR file"
    assert all("PUBLIC_DISPATCH_IRSR" in f for f in files), "Files should match expected pattern"


def test_sra_results_files_discoverable() -> None:
    """Verify we can list live SRA_Results files from NEMWeb."""
    files = list_sra_results_files(limit=5)
    assert len(files) > 0, "Should find at least one SRA_Results file"
    # Each is a tuple (filename, quarter, tranche)
    for fname, quarter, tranche in files:
        assert "PUBLIC_SRRES" in fname
        assert "C202" in quarter  # Calendar quarter format
        assert 1 <= tranche <= 12
