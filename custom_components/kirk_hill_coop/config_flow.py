# Provides UI setup, credential validation, and integration option handling.
# Human checked: No

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KirkHillApiError, KirkHillAuthenticationError, KirkHillHttpClient
from .const import (
    CONF_API_KEY,
    CONF_SCOPE,
    DEFAULT_SCOPE,
    DOMAIN,
    VALID_SCOPES,
)


# Collects and validates a read-only Kirk Hill API key through Home Assistant's UI.
# Human checked: No
class KirkHillConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Kirk Hill Coop setup."""

    VERSION = 1

    # Validates credentials with a lightweight today request before creating the entry.
    # Human checked: No
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = KirkHillHttpClient(
                    async_get_clientsession(self.hass), user_input[CONF_API_KEY]
                )
                await client.fetch_snapshot("today", user_input[CONF_SCOPE])
            except KirkHillAuthenticationError:
                errors["base"] = "invalid_auth"
            except KirkHillApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Kirk Hill Coop", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_SCOPE, default=DEFAULT_SCOPE): vol.In(VALID_SCOPES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # Exposes editable non-secret settings from the integration page.
    # Human checked: No
    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return KirkHillOptionsFlow()


# Allows scope and refresh timing changes without asking for the API key again.
# Human checked: No
class KirkHillOptionsFlow(OptionsFlow):
    """Handle Kirk Hill Coop options."""

    # Stores validated operational settings which trigger a config-entry reload.
    # Human checked: No
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_SCOPE, default=current.get(CONF_SCOPE, DEFAULT_SCOPE)): vol.In(VALID_SCOPES),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
