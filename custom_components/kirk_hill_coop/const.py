# Centralises integration settings so operational values are not buried in logic.
# Human checked: No

DOMAIN = "kirk_hill_coop"
INTEGRATION_NAME = "Kirk Hill Coop"
API_BASE_URL = "https://dashboard.kirkhillcoop.org"
CONF_API_KEY = "api_key"
CONF_SCOPE = "scope"
DEFAULT_SCOPE = "owner"
VALID_SCOPES = ("owner", "site")
RUNTIME_RANGE = "today"
PLATFORMS = ("sensor",)
