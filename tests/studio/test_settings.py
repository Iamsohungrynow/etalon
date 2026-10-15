"""S9: settings defaults, validation, persistence."""

import json

import pytest

from etalon.studio.settings import SETTINGS_FILE, SettingsStore, StudioSettings

CHANGED = {
    "backend": "cuda:0",
    "language": "zh-CN",
    "theme": "light",
    "units": "nm",
    "live_snapshots": True,
}


def test_defaults(client, workspace):
    assert client.get("/api/settings").json() == {
        "backend": "auto",
        "language": "system",
        "theme": "dark",
        "units": "um",
        "live_snapshots": False,
        "workspace": str(workspace),
    }


def test_put_round_trip_persists_everything_but_the_workspace(client, workspace, config_dir):
    response = client.put("/api/settings", json={**CHANGED, "workspace": str(workspace)})
    assert response.status_code == 200
    assert response.json() == {**CHANGED, "workspace": str(workspace)}
    assert client.get("/api/settings").json() == {**CHANGED, "workspace": str(workspace)}
    saved = json.loads((config_dir / SETTINGS_FILE).read_text(encoding="utf-8"))
    assert saved == CHANGED
    assert not list(config_dir.glob("*.tmp"))
    reloaded = SettingsStore(config_dir, workspace.parent).get()
    assert reloaded.model_dump(exclude={"workspace"}) == CHANGED
    assert reloaded.workspace == str(workspace.parent)


def test_put_can_switch_the_workspace(client, workspace, tmp_path):
    other = tmp_path / "other"
    (other / "sub").mkdir(parents=True)
    (other / "sub" / "x.py").write_text("", encoding="utf-8")
    current = client.get("/api/settings").json()
    assert client.put("/api/settings", json={**current, "workspace": str(other)}).status_code == 200
    assert [row["path"] for row in client.get("/api/workspace").json()["simulations"]] == [
        "sub/x.py"
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("theme", "blue"),
        ("language", "fr"),
        ("units", "mm"),
        ("backend", "gpu"),
        ("backend", "cuda:"),
        ("live_snapshots", "maybe"),
        ("extra_field", 1),
    ],
)
def test_bad_values_are_422(client, field, value):
    body = {**client.get("/api/settings").json(), field: value}
    response = client.put("/api/settings", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field


def test_bad_workspace_folders_are_422_with_a_code(client, workspace):
    current = client.get("/api/settings").json()
    a_file = workspace / "file.py"
    a_file.write_text("", encoding="utf-8")
    for value, code in [
        (str(workspace / "missing"), "workspace_not_found"),
        (str(a_file), "workspace_not_a_directory"),
        ("relative/folder", "workspace_not_absolute"),
    ]:
        response = client.put("/api/settings", json={**current, "workspace": value})
        assert response.status_code == 422, value
        detail = response.json()["detail"][0]
        assert (detail["type"], detail["loc"]) == (code, ["body", "workspace"])
    assert client.get("/api/settings").json() == current


@pytest.mark.parametrize("content", ["{broken", '"a string"', '{"theme": "blue"}'])
def test_unreadable_settings_file_gives_defaults_and_a_warning(config_dir, workspace, content):
    config_dir.mkdir(parents=True)
    (config_dir / SETTINGS_FILE).write_text(content, encoding="utf-8")
    with pytest.warns(UserWarning, match="ignoring unreadable Studio settings"):
        settings = SettingsStore(config_dir, workspace).get()
    assert settings == StudioSettings(workspace=str(workspace))


def test_unknown_keys_in_the_file_are_dropped(config_dir, workspace):
    config_dir.mkdir(parents=True)
    saved = {"theme": "light", "from_a_future_version": True, "workspace": "/elsewhere"}
    (config_dir / SETTINGS_FILE).write_text(json.dumps(saved), encoding="utf-8")
    settings = SettingsStore(config_dir, workspace).get()
    assert settings.theme == "light"
    assert settings.workspace == str(workspace)


def test_memory_only_store_writes_nothing(tmp_path, workspace):
    store = SettingsStore(None, workspace)
    store.put(store.get().model_copy(update={"theme": "light"}))
    assert store.get().theme == "light"
    assert not list(tmp_path.rglob(SETTINGS_FILE))
