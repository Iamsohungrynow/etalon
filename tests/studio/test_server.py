"""S11: serving the SPA, and S13: the committed OpenAPI schema."""

from pathlib import Path

import pytest

from etalon.studio.openapi import DEFAULT_PATH, schema_text
from etalon.studio.server import INDEX_HTML_TAG
from tests.studio.conftest import make_client, make_state

INDEX = f"<!doctype html>\n{INDEX_HTML_TAG}<head></head><body>shell</body></html>\n"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "licenses").mkdir()
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "index-abc123.js").write_text("export {};\n", encoding="utf-8")
    (root / "assets" / "font.woff2").write_bytes(b"wOF2")
    (root / "licenses" / "inter-OFL.txt").write_text("SIL OFL 1.1\n", encoding="utf-8")
    (root / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("do not serve", encoding="utf-8")
    return root


@pytest.fixture
def spa(workspace, config_dir, static_dir):
    return make_client(make_state(workspace, config_dir, static_dir=static_dir), token=None)


@pytest.mark.parametrize(
    "path", ["/", "/settings", "/sim/3f2a9c1e04b7/setup", "/modes", "/no/such/page", "/docs"]
)
def test_routes_serve_the_shell_with_theme_and_language(spa, path):
    response = spa.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="en" data-theme="dark">' in response.text
    assert "shell" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_saved_theme_and_language_reach_the_first_paint(workspace, config_dir, static_dir):
    state = make_state(workspace, config_dir, static_dir=static_dir)
    state.settings.put(
        state.settings.get().model_copy(update={"theme": "light", "language": "zh-CN"})
    )
    response = make_client(state, token=None).get("/")
    assert '<html lang="zh-CN" data-theme="light">' in response.text


@pytest.mark.parametrize(
    ("accept", "lang"),
    [("zh-CN,zh;q=0.9,en;q=0.8", "zh-CN"), ("zh-TW", "zh-CN"), ("en-GB,en", "en"), ("", "en")],
)
def test_system_language_follows_accept_language(spa, accept, lang):
    response = spa.get("/", headers={"Accept-Language": accept})
    assert f'<html lang="{lang}" data-theme="dark">' in response.text


def test_hashed_assets_are_immutable_with_explicit_types(spa):
    js = spa.get("/assets/index-abc123.js")
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")
    assert "immutable" in js.headers["cache-control"]
    assert spa.get("/assets/font.woff2").headers["content-type"] == "font/woff2"
    licence = spa.get("/licenses/inter-OFL.txt")
    assert licence.headers["content-type"].startswith("text/plain")
    assert licence.headers["cache-control"] == "no-cache"
    assert spa.get("/favicon.svg").headers["content-type"] == "image/svg+xml"


def test_missing_asset_is_404_not_the_shell(spa):
    response = spa.get("/assets/index-old.js")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2F..%2Fsecret.txt"]
)
def test_no_file_outside_the_static_folder(spa, path):
    assert "do not serve" not in spa.get(path).text


def test_unknown_api_path_is_json_404(workspace, config_dir, static_dir):
    client = make_client(make_state(workspace, config_dir, static_dir=static_dir))
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unbuilt_spa_serves_the_developer_page(workspace, config_dir, tmp_path):
    client = make_client(
        make_state(workspace, config_dir, static_dir=tmp_path / "empty"), token=None
    )
    response = client.get("/settings")
    assert response.status_code == 503
    assert "pnpm --dir studio build" in response.text


def test_committed_openapi_schema_is_current():
    """S13: regenerate with `python -m etalon.studio.openapi`, then `pnpm --dir studio gen:api`."""
    assert DEFAULT_PATH.read_text(encoding="utf-8") == schema_text()
