# Dependency Mapping

## Standalone repo dependencies

### Direct Python packages

- `fastapi`
- `uvicorn`
- `pydantic`
- `pydantic-settings`
- `pandas`
- `numpy`
- `httpx`
- `python-dateutil`

### Why these are separate

The new repository must not depend on importing code from the Vault at runtime. All runtime dependencies must be installed from standard package sources or live inside this repo.

## Vault capability mapping

| Capability | Vault evidence | New-repo treatment |
|---|---|---|
| Live NEM dispatch price fetch | `haimos-app/backend/nem/aemo_fetch.py` | candidate selective adaptation |
| P5MIN / predispatch fetch | `haimos-app/backend/nem/aemo_fetch.py` | candidate selective adaptation |
| Historical backcast signal logic | `haimos-app/backend/nem/aemo_forecast_signals.py` | reimplement around SRA valuation |
| Dispatch/backcast orchestration | `haimos-app/backend/nem/dispatch_runner.py` | reference architecture only |
| API wiring | `haimos-app/backend/server.py` | reimplement in clean FastAPI surface |
| Constraint-driver parsing hints | `haimos-app/backend/nna_parser.py` | defer pending congestion phase |

## Hard isolation rule

No path under `/Users/haimptasznik/Desktop/HaimOS` may be imported by this repository during runtime.
