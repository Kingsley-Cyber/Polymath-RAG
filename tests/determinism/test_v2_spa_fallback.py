"""FRONTEND-V2 real-URL cutover — the SPA client-side-router fallback for the `/v2`
static mount (`orchestrator/main.py::_SPAStaticFilesV2`).

React Router (BrowserRouter) serves paths like /v2/chat, /v2/files client-side; a
direct load or browser refresh on one of those is a REAL GET the server must answer.
Plain `StaticFiles(html=True)` 404s anything that isn't a real file or directory —
confirmed live before this fix (`GET /v2/files -> 404 {"detail":"Not Found"}`) and the
exact defect this test pins closed. A genuinely missing static asset (a stale/broken
build reference) must still 404 — the fallback must not mask that as a false "200 OK,
here's the app shell" response.

Self-contained: builds a synthetic dist/ directory so it does not depend on
frontend-v2/dist existing (git-ignored, may be absent in a fresh clone/CI).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from starlette.applications import Starlette  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from orchestrator.main import _SPAStaticFilesV2  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>spa-shell</body></html>")
    (dist / "assets" / "app-abc123.js").write_text("console.log('app')")

    app = Starlette()
    app.mount("/v2", _SPAStaticFilesV2(directory=str(dist), html=True), name="v2")
    return TestClient(app)


def test_root_serves_index(client):
    r = client.get("/v2/", follow_redirects=False)
    assert r.status_code == 200
    assert "spa-shell" in r.text


def test_a_client_side_route_falls_back_to_index_not_404(client):
    for path in ("/v2/files", "/v2/chat", "/v2/control-plane", "/v2/graph"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, f"{path} must fall back to the SPA shell, not 404"
        assert "spa-shell" in r.text


def test_a_real_asset_is_served_normally_not_by_the_fallback(client):
    r = client.get("/v2/assets/app-abc123.js", follow_redirects=False)
    assert r.status_code == 200
    assert "console.log" in r.text


def test_a_genuinely_missing_asset_still_404s_not_masked_as_the_shell(client):
    """A stale/broken asset reference (bad build, bad cache) must stay visibly
    broken — silently serving the HTML shell instead would hide the real defect."""
    r = client.get("/v2/assets/does-not-exist-xyz.js", follow_redirects=False)
    assert r.status_code == 404


def test_a_path_with_a_dot_that_isnt_a_real_file_also_404s(client):
    """The fallback keys off 'no extension in the last segment' — this documents
    the actual (narrow, deliberate) rule rather than 'any 404 becomes 200'."""
    r = client.get("/v2/some.weird.path", follow_redirects=False)
    assert r.status_code == 404
