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

## What You Get

After installation, the integration creates sensors for:

- `Generation today`
- `Generation last hour`
- `Wind speed`
- `Capacity factor`
- `Active turbines`
- `Site capacity`

It also exposes diagnostic sensors for:

- `Latest data` which is the last successful API poll time from Home Assistant
- `Next hourly check` which is when the delayed last-hour poll is due next

## HACS Installation

1. Open HACS in Home Assistant.
2. Open the menu in the top-right corner.
3. Choose `Custom repositories`.
4. Paste the GitHub repository URL for this project.
5. Choose category `Integration`.
6. Add the repository.
7. Find `Kirk Hill Coop` in HACS and install it.
8. Restart Home Assistant.
9. Go to `Settings -> Devices & services`.
10. Choose `Add integration`.
11. Search for `Kirk Hill Coop`.
12. Paste your read-only API key and finish setup.

## Manual Installation

If you do not want to use HACS yet, copy:

`custom_components/kirk_hill_coop`

into your Home Assistant config folder as:

`custom_components/kirk_hill_coop`

Then restart Home Assistant and add the integration from:

`Settings -> Devices & services -> Add integration`

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

## Before You Install

It is worth testing the API key outside Home Assistant first so you know any
setup problem is in the integration rather than the API itself.

The simplest quick check is a request like:

`https://dashboard.kirkhillcoop.org/api/v1/summary?range=today`

with header:

`Authorization: Bearer <your_api_key>`

Postman worked well during development for this.

## Notes

Import status, API bucket, scope, and per-turbine details are attributes on the
`Generation today` sensor.

