"""The staged start-up (plan-u1 §14.1): the quick app first, the full app once needed."""

import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from etalon.studio.security import TOKEN_HEADER
from etalon.studio.server import create_app
from etalon.studio.staged import StagedApp, needs_full_app
from tests.studio.conftest import BASE_URL, TOKEN, make_state, write_script


@pytest.fixture
def state(workspace, config_dir):
    write_script(workspace, "wg.py")
    return make_state(workspace, config_dir)


class Builder:
    """build_full for StagedApp: counts its calls, and can wait or fail."""

    def __init__(self, state, fail=False):
        self.state = state
        self.fail = fail
        self.calls = 0
        self.release = threading.Event()
        self.release.set()

    def __call__(self) -> FastAPI:
        self.calls += 1
        self.release.wait(10)
        if self.fail:
            raise RuntimeError("full app failed to build (test)")
        return create_app(self.state)


def staged_client(state, builder) -> tuple[StagedApp, TestClient]:
    app = StagedApp(create_app(state, full=False), build_full=builder)
    client = TestClient(app, base_url=BASE_URL)
    client.headers[TOKEN_HEADER] = TOKEN
    return app, client


def paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_quick_app_has_u0_routes_and_no_u1_routes(state):
    quick, full = paths(create_app(state, full=False)), paths(create_app(state))
    assert {"/api/workspace", "/api/settings", "/api/system", "/{path:path}"} <= quick
    assert "/api/templates" not in quick
    assert "/api/templates" in full


def test_quick_app_lists_the_workspace_without_a_job_manager(state):
    with TestClient(create_app(state, full=False), base_url=BASE_URL) as client:
        client.headers[TOKEN_HEADER] = TOKEN
        rows = client.get("/api/workspace").json()["simulations"]
    assert [row["path"] for row in rows] == ["wg.py"]
    assert state._jobs is None


def test_the_page_and_settings_do_not_build_the_full_app(state):
    builder = Builder(state)
    app, client = staged_client(state, builder)
    assert client.get("/").status_code in (200, 503)  # 503: the SPA is not built
    assert client.get("/api/settings").status_code == 200
    assert client.get("/sim/0123456789ab/setup").status_code in (200, 503)
    assert builder.calls == 0
    assert not app.wait_built(0)


def test_the_first_workspace_response_starts_the_build(state):
    builder = Builder(state)
    app, client = staged_client(state, builder)
    assert client.get("/api/workspace").status_code == 200
    assert app.wait_built(30)
    client.get("/api/workspace")
    assert builder.calls == 1


def test_a_u1_request_waits_for_the_build_and_succeeds(state):
    builder = Builder(state)
    builder.release.clear()
    _, client = staged_client(state, builder)
    answers: list[int] = []

    def ask() -> None:
        answers.append(client.get("/api/templates").status_code)

    request = threading.Thread(target=ask)
    request.start()
    request.join(0.5)
    assert request.is_alive(), "the U1 request should wait for the full app"
    builder.release.set()
    request.join(30)
    assert answers == [200]
    assert builder.calls == 1


def test_a_failed_build_answers_500_and_the_workspace_still_works(state, capsys):
    builder = Builder(state, fail=True)
    _, client = staged_client(state, builder)
    response = client.get("/api/templates")
    assert response.status_code == 500
    assert response.json()["code"] == "api_unavailable"
    assert "full app failed to build" in capsys.readouterr().err
    assert client.get("/api/workspace").status_code == 200
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/jobs/x"):
        pass


@pytest.mark.parametrize(
    ("scope", "full"),
    [
        ({"type": "http", "path": "/"}, False),
        ({"type": "http", "path": "/assets/index.js"}, False),
        ({"type": "http", "path": "/sim/0123456789ab/run"}, False),
        ({"type": "http", "path": "/api/workspace"}, False),
        ({"type": "http", "path": "/api/settings"}, False),
        ({"type": "http", "path": "/api/system"}, False),
        ({"type": "http", "path": "/api/templates"}, True),
        ({"type": "http", "path": "/api/openapi.json"}, True),
        ({"type": "http", "path": "/api"}, True),
        ({"type": "http", "path": "/api/workspace/extra"}, True),
        ({"type": "websocket", "path": "/api/jobs/x"}, True),
    ],
)
def test_which_requests_need_the_full_app(scope, full):
    assert needs_full_app(scope) is full
