![Kirk Hill Coop logo](docs/logo.png)

# Kirk Hill Coop for Home Assistant

> [!WARNING]
> This project is not production ready yet.
> It is an in-progress custom integration for testing and iteration, and it may
> change shape, miss edge cases, or break between updates. 
> 
> Use it only if you are happy to test, troubleshoot, and accept rough edges.
>
> This is not an official application from the Kirk Hill Coop

Kirk Hill Coop is a HACS custom integration for importing generation, wind,
and turbine data from the cooperative's read-only API into Home Assistant.

The MVP provides UI setup, API-key validation, configurable live updates from
`/api/v1/current`, delayed whole-hour pulls, separate past-data checks after
midnight, and Home Assistant sensor entities.

## What You Get

After installation, the integration creates sensors for:

- `Current power`
- `Generation today`
- `Generation last hour`
- `Generation yesterday`
- `Generation this month`
- `Generation last month`
- `Wind speed`
- `Capacity factor`
- `Active turbines`
- `Site capacity`

If you set a presumed net saving rate in pence per kWh, it also creates:

- `Savings yesterday`
- `Savings this month`
- `Savings last month`

It also exposes diagnostic sensors for:

- `Last poll` which is the last successful `/api/v1/current` poll time
- `Next poll` which is when the next live `/api/v1/current` poll is due
- `Next hourly check` which is when the delayed last-hour poll is due next
- `Next past data check` which is when the delayed yesterday and monthly poll is due next

## HACS Installation

1. Open HACS in Home Assistant.
2. Open the menu in the top-right corner.
3. Choose `Custom repositories`.
4. Paste [mediaguycouk/kirk_hill_coop](https://github.com/mediaguycouk/kirk_hill_coop).
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

The integration requests `/api/v1/current` on a configurable live schedule of
`5`, `10`, `15`, `30`, or `60` minutes. Each installation keeps using one
stable delayed offset, and the live schedule is anchored to that same offset so
it always lines up cleanly with the hourly archive poll.

The integration also requests the `today` range on the delayed hourly schedule.
Home Assistant records sensor state changes and builds its own long-term
statistics from the point the integration starts running.

Each installation also picks one stable delayed point between `:30` and `:59`
past the hour. After that moment each hour, the integration fetches the most
recently completed whole UK-local hour by calling the API with `range=custom`
and exposes it as a dedicated sensor.

Past-data polling follows a separate schedule. The integration waits until the
first delayed check after UK-local midnight before fetching `yesterday` and the
month totals. If the returned yesterday data is not complete yet, it keeps the
best partial total, advances `Next past data check` by one hour, and retries on
the next delayed hourly poll until `latest_generation_interval_end` reaches the
end of yesterday.

The initial default scope is `owner`, so generation and capacity-factor values
represent the API key holder's share. The integration options can switch this
to `site`.

## Architecture

- `api.py` owns endpoint naming, HTTP requests, authentication, and API error translation.
- `history.py` owns delayed whole-hour and live aligned-schedule calculation in UK local time.
- `models.py` owns typed data transferred between integration layers.
- `coordinator.py` owns live current refreshes, hourly archive refreshes, and separate past-data polling state.
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
| Live refresh interval (minutes) | No | `15` | The integration refreshes `/api/v1/current` every 15 minutes using the stable delayed offset anchor. |
| Presumed net saving rate (pence per kWh) | No | Empty | Savings sensors are not created with values until you provide a rate. |

## Before You Install

It is worth testing the API key outside Home Assistant first so you know any
setup problem is in the integration rather than the API itself.

The simplest quick check is a request like:

`https://dashboard.kirkhillcoop.org/api/v1/current`

with header:

`Authorization: Bearer <your_api_key>`

Postman worked well during development for this.

## Notes

Import status, API bucket, scope, and per-turbine details are attributes on the
`Generation today` sensor.
