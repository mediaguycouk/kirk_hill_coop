![Kirk Hill Coop logo](docs/logo.png)

# Kirk Hill Coop for Home Assistant

> [!WARNING]
> This project is not production ready yet.
> It is an in-progress custom integration for testing and iteration, and it may
> change shape, miss edge cases, or break between updates. Use it only if you
> are happy to test, troubleshoot, and accept rough edges.

Kirk Hill Coop is a HACS custom integration for importing generation, wind,
and turbine data from the cooperative's read-only API into Home Assistant.

The MVP provides UI setup, API-key validation, hourly updates, delayed
whole-hour pulls, and Home Assistant sensor entities.

## Behaviour

The integration requests the `today` range on a fixed hourly schedule. Home
Assistant records sensor state changes and builds its own long-term statistics
from the point the integration starts running.

Each installation also picks one stable delayed point between `:30` and `:59`
past the hour. After that moment each hour, the integration fetches the most
recently completed whole UK-local hour by calling the API with `range=custom`
and exposes it as a dedicated sensor.

The initial default scope is `owner`, so generation and capacity-factor values
represent the API key holder's share. The integration options can switch this
to `site`.

## Architecture

- `api.py` owns HTTP requests, authentication, and API error translation.
- `history.py` owns delayed whole-hour window calculation in UK local time.
- `models.py` owns typed data transferred between integration layers.
- `coordinator.py` owns hourly `today` refreshes and last-hour polling state.
- `config_flow.py` owns UI setup, API-key validation, and options.
- `sensor.py` maps coordinator data to Home Assistant statistics-capable sensors.
- `tests/` mirrors these responsibilities with isolated unit tests.

## Configuration

End users will configure the integration from **Settings > Devices & services**
in Home Assistant. No YAML configuration or environment file will be required.

| Setting | Required | Default | Behaviour when empty or omitted |
| --- | --- | --- | --- |
| API key | Yes | None | Setup cannot continue; the key is validated against the read-only API. |
| Data scope | No | `owner` | Uses the API key holder's share rather than the whole site. |

`.env.example` documents the only development setting:

| Variable | Required | Behaviour when empty or omitted |
| --- | --- | --- |
| `KIRK_HILL_API_KEY` | Only for future live development tests | Live tests are skipped; normal Home Assistant use is unaffected. |

Copy `.env.example` to `.env` only for local development. `.env` is ignored by
Git and must never be committed.

## Local smoke test

Before installing into HACS, you can confirm that a real read-only API key
works from this repository without involving Home Assistant.

1. Copy `.env.example` to `.env`.
2. Replace `KIRK_HILL_API_KEY` with your real read-only key.
3. Run `python scripts/smoke_test.py`.

Optional environment variables:

| Variable | Required | Default | Behaviour when empty or omitted |
| --- | --- | --- | --- |
| `KIRK_HILL_SCOPE` | No | `owner` | Uses the API key holder's share. |
| `KIRK_HILL_RANGE` | No | `today` | Uses the API's current-day range for the smoke test. |

The smoke test prints a short summary showing whether the API responded, how
many generation and wind points were returned, and the latest timestamps seen.
It does not write any Home Assistant state or archive files.

## Installation target

HACS installs `custom_components/kirk_hill_coop` into Home Assistant. Add this
repository as a custom integration repository in HACS, install it, restart Home
Assistant, then add **Kirk Hill Coop** from **Settings > Devices & services**.

The integration creates sensors for generation today, generation last hour,
latest wind speed, capacity factor, active turbines, and site capacity.
Diagnostic sensors expose the last successful API poll time and the next hourly
check.
Import status, API bucket, scope, and per-turbine details are attributes on
the generation-today sensor.

## API contract

The local `openapi.yaml` is the source of truth for the cooperative API. It
defines bearer authentication and the summary, generation, wind-speed, and
turbine endpoints under `https://dashboard.kirkhillcoop.org/api/v1/`.
