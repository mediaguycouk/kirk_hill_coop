# Centralises integration settings so operational values are not buried in logic.
# Human checked: No

DOMAIN = "kirk_hill_coop"
INTEGRATION_NAME = "Kirk Hill Coop"
API_BASE_URL = "https://dashboard.kirkhillcoop.org"
CONF_API_KEY = "api_key"
CONF_LIVE_REFRESH_MINUTES = "live_refresh_minutes"
CONF_PRESUMED_NET_SAVING_RATE_PENCE = "presumed_net_saving_rate_pence"
CONF_SCOPE = "scope"
DEFAULT_SCOPE = "owner"
DEFAULT_LIVE_REFRESH_MINUTES = 15
VALID_SCOPES = ("owner", "site")
VALID_LIVE_REFRESH_MINUTES = (5, 10, 15, 30, 60)
RUNTIME_RANGE = "today"
PLATFORMS = ("sensor",)
