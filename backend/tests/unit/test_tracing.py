from curlchat.core import tracing
from curlchat.db.session import Settings


def test_tracing_is_disabled_by_default(monkeypatch) -> None:
    register_called = False

    def fake_register(**_: object) -> object:
        nonlocal register_called
        register_called = True
        return object()

    monkeypatch.setattr(tracing, "register", fake_register)

    tracing.configure_tracing(Settings(phoenix_tracing_enabled=False))

    assert not register_called


def test_tracing_configures_phoenix_agent_instrumentation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_register(**kwargs: object) -> object:
        captured["register"] = kwargs
        return "tracer-provider"

    monkeypatch.setattr(tracing, "register", fake_register)

    tracing.configure_tracing(
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
