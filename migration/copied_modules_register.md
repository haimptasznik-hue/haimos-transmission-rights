# Copied Modules Register

## Policy

No Vault module is considered copied into this repository unless it is explicitly listed here with its origin, date, rationale, and adaptation notes.

## Current status

No source files have yet been copied from the Vault.

## Planned candidates

| Source path | Decision | Rationale | Notes |
|---|---|---|---|
| `haimos-app/backend/nem/aemo_fetch.py` | Adapt selectively | Strong reusable AEMO/NEM ingestion patterns | Copy only narrow data-source logic after dependency trimming |
| `haimos-app/backend/nem/aemo_forecast_signals.py` | Adapt concepts | Useful scenario and signal ideas | Reimplement SRA-specific logic rather than copy wholesale |
| `haimos-app/backend/nem/dispatch_runner.py` | Reference pattern only | Helpful orchestration shape | Domain mismatch; likely reimplement |
| `haimos-app/backend/server.py` | Do not copy | Monolithic app coupling | Use only as endpoint design reference |
| `haimos-app/backend/nna_parser.py` | Defer | Constraint-context adjacent only | Revisit once congestion driver modeling is prioritized |
