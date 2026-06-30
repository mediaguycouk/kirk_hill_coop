# Provides UI setup, credential validation, and integration option handling.
# Human checked: No

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .api import KirkHillApiError, KirkHillAuthenticationError, KirkHillHttpClient
from .const import (
    CONF_API_KEY,
    CONF_PRESUMED_NET_SAVING_RATE_PENCE,
    CONF_SCOPE,
    DEFAULT_SCOPE,
    DOMAIN,
    VALID_SCOPES,
)


# Parses the optional savings-rate text field into a float while allowing a blank value to disable savings.
# Human checked: No
def _parse_savings_rate(value: Any) -> float | None:
    if value in ("", None):
        return None
    return float(str(value).strip())


# Formats the saved numeric value back into a simple text-field default for Home Assistant's UI renderer.
# Human checked: No
def _format_savings_rate(value: float | str) -> str:
    if value in ("", None):
        return ""
    return str(value)


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
                await self._validate_api_key(user_input[CONF_API_KEY], user_input[CONF_SCOPE])
                presumed_net_saving_rate_pence = _parse_savings_rate(
                    user_input.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE, "")
                )
            except ValueError:
                errors[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = "invalid_savings_rate"
            except KirkHillAuthenticationError:
                errors["base"] = "invalid_auth"
            except KirkHillApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                cleaned = {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_SCOPE: user_input[CONF_SCOPE],
                }
                if presumed_net_saving_rate_pence is not None:
                    cleaned[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = presumed_net_saving_rate_pence
                return self.async_create_entry(title="Kirk Hill Coop", data=cleaned)

        schema = self._build_reconfigure_schema()
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # Reconfigures an existing entry from the UI cog, including credentials and savings settings.
    # Human checked: No
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        current = {**entry.data, **entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._validate_api_key(user_input[CONF_API_KEY], user_input[CONF_SCOPE])
                presumed_net_saving_rate_pence = _parse_savings_rate(
                    user_input.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE, "")
                )
            except ValueError:
                errors[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = "invalid_savings_rate"
            except KirkHillAuthenticationError:
                errors["base"] = "invalid_auth"
            except KirkHillApiError:
                errors["base"] = "cannot_connect"
            else:
                options = {
                    CONF_SCOPE: user_input[CONF_SCOPE],
                }
                if presumed_net_saving_rate_pence is not None:
                    options[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = presumed_net_saving_rate_pence
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_SCOPE: user_input[CONF_SCOPE],
                    },
                    options=options,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_reconfigure_schema(
                api_key=current.get(CONF_API_KEY, ""),
                scope=current.get(CONF_SCOPE, DEFAULT_SCOPE),
                presumed_net_saving_rate_pence=current.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE, ""),
            ),
            errors=errors,
        )

    # Builds the shared schema for setup and reconfigure flows.
    # Human checked: No
    def _build_reconfigure_schema(
        self,
        *,
        api_key: str = "",
        scope: str = DEFAULT_SCOPE,
        presumed_net_saving_rate_pence: float | str = "",
    ) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=api_key): str,
                vol.Required(CONF_SCOPE, default=scope): vol.In(VALID_SCOPES),
                vol.Optional(
                    CONF_PRESUMED_NET_SAVING_RATE_PENCE,
                    default=_format_savings_rate(presumed_net_saving_rate_pence),
                ): TextSelector(TextSelectorConfig()),
            }
        )

    # Validates credentials with the same lightweight today request used during initial setup.
    # Human checked: No
    async def _validate_api_key(self, api_key: str, scope: str) -> None:
        client = KirkHillHttpClient(async_get_clientsession(self.hass), api_key)
        await client.fetch_snapshot("today", scope)

    # Exposes editable non-secret settings from the integration page.
    # Human checked: No
    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return KirkHillOptionsFlow(config_entry)


# Allows scope and refresh timing changes without asking for the API key again.
# Human checked: No
class KirkHillOptionsFlow(OptionsFlow):
    """Handle Kirk Hill Coop options."""

    # Stores the linked config entry without using the deprecated public setter so the options UI can open safely.
    # Human checked: No
    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    # Stores validated operational settings which trigger a config-entry reload.
    # Human checked: No
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                presumed_net_saving_rate_pence = _parse_savings_rate(
                    user_input.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE, "")
                )
            except ValueError:
                errors[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = "invalid_savings_rate"
            else:
                cleaned = {
                    CONF_SCOPE: user_input[CONF_SCOPE],
                }
                if presumed_net_saving_rate_pence is not None:
                    cleaned[CONF_PRESUMED_NET_SAVING_RATE_PENCE] = presumed_net_saving_rate_pence
                return self.async_create_entry(title="", data=cleaned)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_SCOPE, default=current.get(CONF_SCOPE, DEFAULT_SCOPE)): vol.In(VALID_SCOPES),
                vol.Optional(
                    CONF_PRESUMED_NET_SAVING_RATE_PENCE,
                    default=_format_savings_rate(current.get(CONF_PRESUMED_NET_SAVING_RATE_PENCE, "")),
                ): TextSelector(TextSelectorConfig()),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
