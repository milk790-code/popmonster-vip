from datetime import datetime, timedelta, timezone

from tests.conftest import login_as


class FakeRedis:
    def __init__(self, value=None):
        self.value = value
        self.writes = []

    def set(self, key, value, ex):
        self.writes.append((key, value, ex))
        self.value = value

    def get(self, _key):
        return self.value


def test_write_worker_heartbeat_uses_private_redis_with_ttl(monkeypatch):
    from app.scheduler import worker_heartbeat

    fake = FakeRedis()
    monkeypatch.setattr(worker_heartbeat, "_redis", lambda: fake)
    payload = worker_heartbeat.write_worker_heartbeat(
        now=datetime(2026, 7, 29, tzinfo=timezone.utc)
    )
    assert payload["component"] == "worker"
    assert payload["status"] == "ok"
    assert fake.writes[0][0] == "social_distributor:worker:heartbeat"
    assert fake.writes[0][2] == 180


def test_worker_heartbeat_endpoint_requires_login(client):
    assert client.get("/api/system/worker-heartbeat").status_code == 401


def test_worker_heartbeat_endpoint_reports_fresh_private_state(client, monkeypatch):
    from app.api import system as system_api

    stamp = datetime.now(timezone.utc) - timedelta(seconds=10)
    fake = FakeRedis(
        '{"component":"worker","status":"ok","observed_at":"'
        + stamp.isoformat().replace("+00:00", "Z")
        + '","release":"abc123"}'
    )
    monkeypatch.setattr(system_api, "_redis", lambda: fake)
    login_as(client, 1)
    response = client.get("/api/system/worker-heartbeat")
    assert response.status_code == 200
    assert response.get_json()["fresh"] is True


def test_worker_heartbeat_endpoint_fails_closed_when_stale(client, monkeypatch):
    from app.api import system as system_api

    stamp = datetime.now(timezone.utc) - timedelta(minutes=10)
    fake = FakeRedis(
        '{"component":"worker","status":"ok","observed_at":"'
        + stamp.isoformat().replace("+00:00", "Z")
        + '"}'
    )
    monkeypatch.setattr(system_api, "_redis", lambda: fake)
    login_as(client, 1)
    response = client.get("/api/system/worker-heartbeat")
    assert response.status_code == 503
    assert response.get_json()["status"] == "stale"
