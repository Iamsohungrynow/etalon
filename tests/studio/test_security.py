"""S2–S5: token, Host check, browser guards, telemetry off."""

import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from etalon.studio.security import TOKEN_FILE, load_or_create_token
from tests.studio.conftest import BASE_URL, make_client, make_state


# S2 ----------------------------------------------------------------------------------
@pytest.mark.parametrize("token", [None, "wrong", ""])
def test_api_without_the_right_token_is_401(workspace, config_dir, token):
    client = make_client(make_state(workspace, config_dir), token=token)
    for path in ("/api/workspace", "/api/settings", "/api/system", "/api/openapi.json"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "unauthorized"


def test_api_with_the_token_is_200(client):
    assert client.get("/api/workspace").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200


def test_pages_need_no_token(workspace, config_dir):
    client = make_client(make_state(workspace, config_dir), token=None)
    # The SPA shell holds no data; without a built SPA it is the developer page.
    assert client.get("/").status_code in (200, 503)


def test_token_is_created_once_and_reused(config_dir):
    first = load_or_create_token(config_dir)
    assert len(first) >= 40
    assert (config_dir / TOKEN_FILE).read_text(encoding="ascii").strip() == first
    assert load_or_create_token(config_dir) == first


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_token_file_is_private(config_dir):
    load_or_create_token(config_dir)
    assert os.stat(config_dir / TOKEN_FILE).st_mode & 0o777 == 0o600


def test_token_env_override(config_dir, monkeypatch):
    monkeypatch.setenv("ETALON_STUDIO_TOKEN", "from-env")
    assert load_or_create_token(config_dir) == "from-env"
    assert not (config_dir / TOKEN_FILE).exists()


# S3 ----------------------------------------------------------------------------------
@pytest.mark.parametrize("host", ["evil.example", "evil.example:8787", "127.0.0.1:9999", ""])
def test_foreign_host_is_400(client, host):
    response = client.get("/api/settings", headers={"Host": host})
    assert response.status_code == 400
    assert response.json()["code"] == "bad_host"


@pytest.mark.parametrize("host", ["127.0.0.1:8787", "localhost:8787", "LOCALHOST:8787"])
def test_local_host_is_accepted(client, host):
    assert client.get("/api/settings", headers={"Host": host}).status_code == 200


# S4 ----------------------------------------------------------------------------------
def test_no_cors_headers(client):
    preflight = client.options(
        "/api/settings",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "x-etalon-token",
        },
    )
    assert not any(h.lower().startswith("access-control-") for h in preflight.headers)
    response = client.get("/api/settings", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_swagger_and_redoc_are_not_served(client):
    for path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
        body = client.get(path).text.lower()
        assert "swagger" not in body and "redoc" not in body, path


def test_html_has_a_content_security_policy(client):
    policy = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "http" not in policy  # no other origin is allowed anywhere


# S5 ----------------------------------------------------------------------------------
def test_environment_cannot_turn_on_fastapi_telemetry(workspace, config_dir, monkeypatch, caplog):
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
    # Control: a plain FastAPI app does try to set up OTLP export here, and logs that
    # it failed because the exporter is not installed. If this control stops logging,
    # FastAPI changed how it exports: re-check TELEMETRY_OFF in server.py.
    with caplog.at_level(logging.WARNING, logger="fastapi"):
        with TestClient(FastAPI(), base_url=BASE_URL):
            pass
    assert "automatic telemetry" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="fastapi"):
        with make_client(make_state(workspace, config_dir)) as client:
            assert client.get("/api/settings").status_code == 200
    assert "telemetry" not in caplog.text.lower()


def test_no_spans_even_with_a_tracer_provider_installed(tmp_path: Path):
    # Global OpenTelemetry state can be set once per process: use a fresh one.
    script = textwrap.dedent(
        f"""
        from pathlib import Path
        from opentelemetry import trace
        from fastapi.testclient import TestClient

        calls = []

        class Recording(trace.TracerProvider):
            def get_tracer(self, *args, **kwargs):
                calls.append(args)
                return trace.NoOpTracer()

        trace.set_tracer_provider(Recording())
        from etalon.studio.server import StudioState, create_app
        from etalon.studio.settings import SettingsStore
        from tests.studio.conftest import FakeProbe

        state = StudioState(SettingsStore(None, Path(r"{tmp_path}")), FakeProbe(), "t", 8787)
        with TestClient(create_app(state), base_url="http://127.0.0.1:8787") as client:
            assert client.get("/api/settings", headers={{"X-Etalon-Token": "t"}}).status_code == 200
        print("calls", len(calls))
        """
    )
    root = Path(__file__).resolve().parents[2]
    out = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=root,
        timeout=120,
        check=True,
    )
    assert out.stdout.strip().splitlines()[-1] == "calls 0"
