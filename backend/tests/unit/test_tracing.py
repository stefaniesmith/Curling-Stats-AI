from fastapi import FastAPI

from curlchat.core import tracing
from curlchat.db.session import Settings


def test_tracing_is_disabled_by_default(monkeypatch) -> None:
    register_called = False

    def fake_register(**_: object) -> object:
        nonlocal register_called
        register_called = True
        return object()

    monkeypatch.setattr(tracing, "register", fake_register)

    tracing.configure_tracing(FastAPI(), Settings(phoenix_tracing_enabled=False))

    assert not register_called


def test_tracing_configures_phoenix_and_excludes_health(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_register(**kwargs: object) -> object:
        captured["register"] = kwargs
        return "tracer-provider"

    def fake_instrument_app(app: FastAPI, **kwargs: object) -> None:
        captured["app"] = app
        captured["instrument"] = kwargs

    app = FastAPI()
    monkeypatch.setattr(tracing, "register", fake_register)
    monkeypatch.setattr(tracing.FastAPIInstrumentor, "instrument_app", fake_instrument_app)

    tracing.configure_tracing(
        app,
        Settings(
            phoenix_tracing_enabled=True,
            phoenix_collector_endpoint="http://phoenix.local:6006/v1/traces",
            phoenix_project_name="curlchat-test",
        ),
    )

    assert captured["register"] == {
        "project_name": "curlchat-test",
        "endpoint": "http://phoenix.local:6006/v1/traces",
        "protocol": "http/protobuf",
        "auto_instrument": True,
        "batch": True,
    }
    assert captured["app"] is app
    assert captured["instrument"] == {
        "tracer_provider": "tracer-provider",
        "excluded_urls": "/health",
    }
