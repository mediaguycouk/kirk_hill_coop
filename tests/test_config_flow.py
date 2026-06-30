# Verifies options-flow and reconfigure handling for the optional presumed net saving rate.
# Human checked: No

from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.kirk_hill_coop.config_flow import KirkHillConfigFlow, KirkHillOptionsFlow
from custom_components.kirk_hill_coop.const import CONF_API_KEY, CONF_PRESUMED_NET_SAVING_RATE_PENCE, CONF_SCOPE


# Confirms the options form includes the optional presumed net saving rate field with the saved default.
# Human checked: No
@pytest.mark.asyncio
async def test_options_form_includes_presumed_net_saving_rate_default() -> None:
    flow = KirkHillOptionsFlow(
        Mock(data={CONF_SCOPE: "owner"}, options={CONF_PRESUMED_NET_SAVING_RATE_PENCE: 12.5})
    )

    result = await flow.async_step_init()
    validated = result["data_schema"]({CONF_SCOPE: "owner", CONF_PRESUMED_NET_SAVING_RATE_PENCE: "12.5"})

    assert result["type"] == "form"
    assert validated[CONF_PRESUMED_NET_SAVING_RATE_PENCE] == "12.5"


# Confirms blank savings-rate input disables savings by removing the option from stored data.
# Human checked: No
@pytest.mark.asyncio
async def test_options_flow_removes_blank_savings_rate() -> None:
    flow = KirkHillOptionsFlow(Mock(data={CONF_SCOPE: "owner"}, options={}))

    result = await flow.async_step_init({CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: ""})

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCOPE: "site"}


# Confirms numeric savings-rate input is preserved for later coordinator use.
# Human checked: No
@pytest.mark.asyncio
async def test_options_flow_keeps_numeric_savings_rate() -> None:
    flow = KirkHillOptionsFlow(Mock(data={CONF_SCOPE: "owner"}, options={}))

    result = await flow.async_step_init({CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: "15.0"})

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: 15.0}


# Confirms reconfigure shows the API key, scope, and savings-rate fields for existing entries.
# Human checked: No
@pytest.mark.asyncio
async def test_reconfigure_form_includes_savings_rate() -> None:
    flow = KirkHillConfigFlow()
    flow._get_reconfigure_entry = Mock(
        return_value=Mock(
            data={CONF_API_KEY: "token", CONF_SCOPE: "owner"},
            options={CONF_PRESUMED_NET_SAVING_RATE_PENCE: 12.5},
        )
    )

    result = await flow.async_step_reconfigure()
    validated = result["data_schema"](
        {
            CONF_API_KEY: "token",
            CONF_SCOPE: "owner",
            CONF_PRESUMED_NET_SAVING_RATE_PENCE: "12.5",
        }
    )

    assert result["type"] == "form"
    assert validated[CONF_API_KEY] == "token"
    assert validated[CONF_PRESUMED_NET_SAVING_RATE_PENCE] == "12.5"


# Confirms reconfigure writes the API key back to entry data and keeps savings in options.
# Human checked: No
@pytest.mark.asyncio
async def test_reconfigure_updates_data_and_options() -> None:
    entry = Mock(data={CONF_API_KEY: "old", CONF_SCOPE: "owner"}, options={})
    flow = KirkHillConfigFlow()
    flow._get_reconfigure_entry = Mock(return_value=entry)
    flow._validate_api_key = AsyncMock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_mismatch = Mock()
    flow.async_update_reload_and_abort = Mock(return_value={"type": "abort", "reason": "reconfigure_successful"})

    result = await flow.async_step_reconfigure(
        {
            CONF_API_KEY: "new-token",
            CONF_SCOPE: "site",
            CONF_PRESUMED_NET_SAVING_RATE_PENCE: "15.0",
        }
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    flow.async_update_reload_and_abort.assert_called_once_with(
        entry,
        data_updates={CONF_API_KEY: "new-token", CONF_SCOPE: "site"},
        options={CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: 15.0},
    )


# Confirms invalid savings-rate text comes back as a field error instead of crashing the form serializer.
# Human checked: No
@pytest.mark.asyncio
async def test_options_flow_rejects_invalid_savings_rate_text() -> None:
    flow = KirkHillOptionsFlow(Mock(data={CONF_SCOPE: "owner"}, options={}))

    result = await flow.async_step_init({CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: "abc"})

    assert result["type"] == "form"
    assert result["errors"] == {CONF_PRESUMED_NET_SAVING_RATE_PENCE: "invalid_savings_rate"}
