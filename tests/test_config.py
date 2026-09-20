import os
import pytest


def test_production_requires_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import importlib
    import config
    importlib.reload(config)
    with pytest.raises(RuntimeError):
        config.Config.validate()


def test_development_allows_missing_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import importlib
    import config
    importlib.reload(config)
    config.Config.validate()
