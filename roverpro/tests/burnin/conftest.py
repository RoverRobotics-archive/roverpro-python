import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config.inicfg["log_cli"] = "true"
    config.inicfg["log_cli_level"] = "NOTSET"
    config.inicfg["log_cli_format"] = "%(asctime)s %(levelname)s %(message)s"
