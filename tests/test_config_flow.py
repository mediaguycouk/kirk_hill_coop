# Verifies options-flow handling for the optional presumed net saving rate.
# Human checked: No

from unittest.mock import Mock

import pytest

from custom_components.kirk_hill_coop.config_flow import KirkHillOptionsFlow
from custom_components.kirk_hill_coop.const import CONF_PRESUMED_NET_SAVING_RATE_PENCE, CONF_SCOPE


# Confirms the options form includes the optional presumed net saving rate field with the saved default.
# Human checked: No
@pytest.mark.asyncio
async def test_options_form_includes_presumed_net_saving_rate_default() -> None:
    flow = KirkHillOptionsFlow()
    flow._config_entry = Mock(data={CONF_SCOPE: "owner"}, options={CONF_PRESUMED_NET_SAVING_RATE_PENCE: 12.5})

    result = await flow.async_step_init()
    validated = result["data_schema"]({CONF_SCOPE: "owner", CONF_PRESUMED_NET_SAVING_RATE_PENCE: 12.5})

    assert result["type"] == "form"
    assert validated[CONF_PRESUMED_NET_SAVING_RATE_PENCE] == 12.5


# Confirms blank savings-rate input disables savings by removing the option from stored data.
# Human checked: No
@pytest.mark.asyncio
async def test_options_flow_removes_blank_savings_rate() -> None:
    flow = KirkHillOptionsFlow()
    flow._config_entry = Mock(data={CONF_SCOPE: "owner"}, options={})

    result = await flow.async_step_init({CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: ""})

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCOPE: "site"}


# Confirms numeric savings-rate input is preserved for later coordinator use.
# Human checked: No
@pytest.mark.asyncio
async def test_options_flow_keeps_numeric_savings_rate() -> None:
    flow = KirkHillOptionsFlow()
    flow._config_entry = Mock(data={CONF_SCOPE: "owner"}, options={})

    result = await flow.async_step_init({CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: 15.0})

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCOPE: "site", CONF_PRESUMED_NET_SAVING_RATE_PENCE: 15.0}
