# Reserves shared deterministic fixtures, including controllable UK-aware time.
# Human checked: No

import sys

import pytest
import pytest_socket


# Re-enables sockets during test setup because Home Assistant's Windows event loop needs them.
# Human checked: No
@pytest.hookimpl(trylast=True)
def pytest_runtest_setup() -> None:
    pytest_socket.enable_socket()


# Supplies a Windows-safe event loop policy so Home Assistant tests do not fail during loop creation.
# Human checked: No
@pytest.fixture
def event_loop_policy():
    pytest_socket.enable_socket()
    if sys.platform == "win32":
        return pytest.importorskip("asyncio").WindowsSelectorEventLoopPolicy()
    return pytest.importorskip("asyncio").DefaultEventLoopPolicy()
