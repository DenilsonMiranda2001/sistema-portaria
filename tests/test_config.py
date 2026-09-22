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


def test_production_cookie_security_cannot_be_disabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    source = Path("config.py").read_text(encoding="utf-8")
    assert 'SESSION_COOKIE_SECURE = True if APP_ENV == "production"' in source


def test_database_pool_bounds_are_validated():
    source = Path("config.py").read_text(encoding="utf-8")
    assert "cls.DB_POOL_MIN < 1" in source
    assert "cls.DB_POOL_MAX < cls.DB_POOL_MIN" in source
