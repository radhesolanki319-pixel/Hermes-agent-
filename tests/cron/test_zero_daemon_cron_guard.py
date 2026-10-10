import threading
import pytest
from cron.scheduler_thread import SupervisedTickerThread


def test_zero_daemon_suppresses_cron_ticker(monkeypatch):
    """When ZERO_DAEMON_MODE is set or on Android, cron ticker does not start a background thread."""
    monkeypatch.setenv("ZERO_DAEMON_MODE", "1")
    monkeypatch.setattr("hermes_platform.host.facts.is_android", lambda: True)

    executed = []
    stop_event = threading.Event()
    ticker = SupervisedTickerThread(
        target=lambda: executed.append(1),
        stop_event=stop_event,
        name="test-cron-ticker",
    )

    ticker.start()
    assert not ticker.is_alive()
    assert len(executed) == 0


@pytest.mark.asyncio
async def test_zero_daemon_suppresses_gateway_server(monkeypatch):
    """When ZERO_DAEMON_MODE is set or on Android, start_gateway refuses to spin up background server."""
    from gateway.run import start_gateway

    monkeypatch.setenv("ZERO_DAEMON_MODE", "1")
    monkeypatch.setattr("hermes_platform.host.facts.is_android", lambda: True)

    result = await start_gateway()
    assert result is False
