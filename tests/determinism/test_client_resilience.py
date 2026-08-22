"""P0-C — stale-connection recovery for sidecar clients.

A sidecar restart leaves half-open sockets in the client's pool. Reusing
one blocks or fails indefinitely; that is how a projection stall became a
16-hour outage. Every request must therefore be bounded, must rebuild the
pool on a transport fault, and must end in a TYPED terminal error rather
than an unbounded wait.
"""
import httpx
import pytest

from polymath_shared.clients import SidecarClient, SidecarUnavailable


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=httpx.Request("POST", "http://x"),
                response=httpx.Response(self.status_code))


class _FlakyClient:
    """Fails `fail_times` with a transport error, then succeeds."""

    def __init__(self, fail_times, exc=httpx.ConnectError("boom")):
        self.fail_times = fail_times
        self.exc = exc
        self.calls = 0
        self.closed = 0

    def post(self, path, **kw):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        return _Resp()

    get = post

    def close(self):
        self.closed += 1


def _client(monkeypatch, fake):
    c = SidecarClient.__new__(SidecarClient)
    c.base_url = "http://sidecar"
    c._timeout = httpx.Timeout(30.0, connect=5.0, pool=5.0)
    c._client = fake
    c._pin_release = None
    c._require_pin = False
    monkeypatch.setattr(c, "_reset_pool", lambda: (fake.close(), None)[1])
    return c


def test_timeouts_are_bounded_on_every_phase():
    """A float timeout leaves connect/pool as slow as read; a dead host
    must be detected in seconds, not in the inference budget."""
    c = SidecarClient("http://127.0.0.1:9", timeout=120.0, require_pin=False)
    try:
        t = c._timeout
        assert t.connect <= 5.0
        assert t.pool <= 5.0
        assert t.read == 120.0
    finally:
        c.close()


def test_transport_fault_retries_on_a_rebuilt_pool(monkeypatch):
    fake = _FlakyClient(fail_times=1)
    c = _client(monkeypatch, fake)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    assert c.request("POST", "/infer", json={}).json() == {"ok": True}
    assert fake.calls == 2
    assert fake.closed == 1, "pool was not invalidated between attempts"


def test_terminal_failure_is_typed_not_an_infinite_wait(monkeypatch):
    fake = _FlakyClient(fail_times=99)
    c = _client(monkeypatch, fake)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    with pytest.raises(SidecarUnavailable) as e:
        c.request("POST", "/infer", json={}, attempts=3)
    assert fake.calls == 3
    assert "unreachable after 3 attempts" in str(e.value)


@pytest.mark.parametrize("exc", [
    httpx.ConnectError("x"), httpx.ConnectTimeout("x"), httpx.ReadTimeout("x"),
    httpx.PoolTimeout("x"), httpx.RemoteProtocolError("x"), httpx.ReadError("x"),
])
def test_every_stale_socket_symptom_is_retryable(monkeypatch, exc):
    fake = _FlakyClient(fail_times=1, exc=exc)
    c = _client(monkeypatch, fake)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    assert c.request("POST", "/infer", json={}).json() == {"ok": True}


def test_client_error_is_not_retried(monkeypatch):
    """4xx is our own bug; retrying it wastes the retry budget."""
    class _Client400:
        calls = 0

        def post(self, path, **kw):
            _Client400.calls += 1
            return _Resp(status=400)

        def close(self):
            pass

    c = _client(monkeypatch, _Client400())
    with pytest.raises(httpx.HTTPStatusError):
        c.request("POST", "/infer", json={})
    assert _Client400.calls == 1


def test_server_error_is_retried_then_raised(monkeypatch):
    """5xx can be a sidecar mid-restart, so it is worth one more try."""
    class _Client503:
        calls = 0

        def post(self, path, **kw):
            _Client503.calls += 1
            return _Resp(status=503)

        def close(self):
            pass

    c = _client(monkeypatch, _Client503())
    monkeypatch.setattr("time.sleep", lambda *_: None)
    with pytest.raises(httpx.HTTPStatusError):
        c.request("POST", "/infer", json={}, attempts=3)
    assert _Client503.calls == 3


def test_inference_clients_are_connect_fast_and_read_patient():
    """Contended GPU inference is legitimately slow: a 32-text embed
    batch measured ~2.4s idle and ~38s while extraction ran, so the
    generic 30s budget failed every attempt of a projection and burned
    the ticket. Connect stays short so a dead sidecar is still caught
    immediately; only the read phase is patient."""
    from polymath_shared.clients import (
        INFERENCE_READ_TIMEOUT_S, EmbedderClient, GlinerClient,
        SpacySyntaxClient,
    )
    assert INFERENCE_READ_TIMEOUT_S >= 120.0
    for factory in (EmbedderClient, GlinerClient, SpacySyntaxClient):
        c = factory()
        try:
            assert c._timeout.read == INFERENCE_READ_TIMEOUT_S
            assert c._timeout.connect <= 5.0
            assert c._timeout.pool <= 5.0
        finally:
            c.close()


def test_routing_projection_checkpoints_so_a_retry_resumes():
    """A full corpus routing pass is hours of embedding. Receipts written
    only at the end mean any failure discards every completed batch:
    three attempts once burned 1,705 embed calls without finishing one
    pass. Slices must be checkpointed on their own connection so a retry
    resumes instead of restarting."""
    import ast
    import inspect

    from workers import project_qdrant_worker as w

    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(w._write_routing_points)))
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_checkpoint_routing" in calls, "routing pass does not checkpoint"
    assert "_write_routing_slice" in calls, "routing pass is not sliced"

    # the checkpoint must open its OWN transaction, not reuse the stage's
    cp = inspect.getsource(w._checkpoint_routing)
    assert "with tx()" in cp, (
        "checkpoint must commit independently of the stage transaction, "
        "which rolls back on failure")
