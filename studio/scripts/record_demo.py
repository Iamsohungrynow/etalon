"""Record the static demo (docs/plan-demo.md): real M0 runs of the Studio templates.

    .venv/Scripts/python studio/scripts/record_demo.py      (Windows)
    .venv/bin/python studio/scripts/record_demo.py          (POSIX)

It starts Studio's own server in-process (FastAPI's TestClient, no port) on a fresh
workspace, creates one simulation per template through ``POST /api/simulations``, runs
each through ``POST /api/simulations/{id}/run`` on the default backend (a CUDA GPU when
there is one) and records every WebSocket frame with its arrival time. It then makes
every GET the UI can make and writes the answers, byte for byte, under
``studio/demo-data/`` with a ``manifest.json`` that maps each request to its file.

The demo build (``pnpm build:demo``) ships that folder and answers the UI's requests
from it, so every number on the demo page is the solver's. Before writing, the
workspace's absolute path is replaced by ``~/etalon-demo`` and other local paths are
stripped; the script fails if a local path is left in any answer.
"""

import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from etalon.studio.contract import TemplateId
from etalon.studio.security import TOKEN_HEADER
from etalon.studio.server import StudioState, create_app
from etalon.studio.settings import SettingsStore
from etalon.studio.system import GpuProbe

STUDIO_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDIO_DIR.parent
OUT = STUDIO_DIR / "demo-data"
TOKEN = "demo-recorder"
BASE_URL = "http://127.0.0.1:8787"
DISPLAY_WORKSPACE = "~/etalon-demo"
QUANTITIES = ("abs", "real", "imag", "phase")
MAX_SNAPSHOTS = 90
"""Live frames kept per run, evenly spaced (the last always), to keep the site small."""

TEMPLATES: tuple[TemplateId, ...] = (
    "strip_waveguide",
    "sharp_bend",
    "phc_waveguide",
    "vacuum_pulse",
)


class Recorder:
    def __init__(self, client: TestClient, out: Path, scrub: list[tuple[str, str]]) -> None:
        self.client = client
        self.out = out
        self.scrub = scrub
        self.responses: dict[str, dict[str, Any]] = {}

    def clean(self, text: str) -> str:
        for local, shown in self.scrub:
            text = text.replace(local, shown)
        return text

    def write(self, data: bytes, suffix: str) -> str:
        digest = hashlib.sha256(data).hexdigest()[:16]
        relative = f"r/{digest}{suffix}"
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative

    def get(self, path: str, **query: Any) -> Any:
        """GET ``path`` and keep its answer under the key the demo adapter will look up."""
        response = self.client.get(path, params=query or None)
        key = request_key("GET", path, query)
        media = response.headers.get("content-type", "").split(";")[0]
        if media == "application/json":
            body = self.clean(response.text).encode("utf-8")
            suffix = ".json"
        else:
            body = response.content
            suffix = ".bin"
        self.responses[key] = {
            "file": self.write(body, suffix),
            "status": response.status_code,
            "type": media,
        }
        return json.loads(body) if media == "application/json" else None


def request_key(method: str, path: str, query: dict[str, Any] | None = None) -> str:
    """``GET /api/x?a=1&b=2``, query sorted; studio/src/demo/staticApi.ts builds the same."""
    if not query:
        return f"{method} {path}"
    pairs = "&".join(f"{name}={query[name]}" for name in sorted(query))
    return f"{method} {path}?{pairs}"


def record_job(client: TestClient, recorder: Recorder, sim_id: str) -> dict[str, Any]:
    started_at = time.monotonic()
    response = client.post(f"/api/simulations/{sim_id}/run")
    assert response.status_code == 202, response.text
    job = response.json()
    frames: list[dict[str, Any]] = []
    snapshots: list[bytes] = []
    with client.websocket_connect(
        f"ws://127.0.0.1:8787/api/jobs/{job['job_id']}",
        subprotocols=["etalon.v1", f"token.{TOKEN}"],
    ) as socket:
        while True:
            frame = socket.receive()
            t = round(time.monotonic() - started_at, 3)
            if frame.get("bytes") is not None:
                frames.append({"t": t, "snapshot": len(snapshots)})
                snapshots.append(frame["bytes"])
                continue
            message = json.loads(recorder.clean(frame["text"]))
            frames.append({"t": t, "message": message})
            if message["type"] == "done":
                break
    done = frames[-1]["message"]
    if done["status"] != "done":
        raise RuntimeError(f"{sim_id}: the run ended {done['status']}: {done.get('error')}")

    # Thin the live frames, then store them back to back in one file.
    keep = set(range(len(snapshots)))
    if len(snapshots) > MAX_SNAPSHOTS:
        step = (len(snapshots) - 1) / (MAX_SNAPSHOTS - 1)
        keep = {round(i * step) for i in range(MAX_SNAPSHOTS)}
    blob = bytearray()
    kept: list[dict[str, Any]] = []
    for frame in frames:
        if "snapshot" not in frame:
            kept.append(frame)
        elif frame["snapshot"] in keep:
            data = snapshots[frame["snapshot"]]
            kept.append({"t": frame["t"], "snapshot": [len(blob), len(data)]})
            blob += data
    return {
        "result_id": job["result_id"],
        "frames": recorder.write(json.dumps({"frames": kept}).encode("utf-8"), ".json"),
        "snapshots": recorder.write(bytes(blob), ".bin"),
        "snapshot_count": len(keep),
        "recorded_snapshot_count": len(snapshots),
    }


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="etalon-demo-"))
    workspace = root / "etalon-demo"
    workspace.mkdir()
    config_dir = root / "config"
    home = str(Path.home())
    local = str(workspace)
    scrub: list[tuple[str, str]] = []
    for path, shown in ((local, DISPLAY_WORKSPACE), (str(REPO_ROOT), "etalon"), (home, "~")):
        scrub.append((json.dumps(path)[1:-1], shown))  # as it appears inside JSON strings
        scrub.append((path, shown))
        scrub.append((path.replace("\\", "/"), shown))
    probe = GpuProbe().start()
    state = StudioState(
        settings=SettingsStore(config_dir, workspace),
        probe=probe,
        token=TOKEN,
        port=8787,
        config_dir=config_dir,
    )
    state.settings.put(
        state.settings.get().model_copy(update={"backend": "auto", "live_snapshots": True})
    )
    client = TestClient(create_app(state), base_url=BASE_URL)
    client.headers[TOKEN_HEADER] = TOKEN

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    recorder = Recorder(client, OUT, scrub)
    try:
        print("GPU:", json.dumps(probe.result().get("devices")), flush=True)  # waits for it
        for template in TEMPLATES:
            response = client.post(
                "/api/simulations", json={"template": template, "name": template}
            )
            assert response.status_code == 201, response.text
        rows = client.get("/api/workspace").json()["simulations"]
        ids = {row["path"]: row["id"] for row in rows}

        jobs: dict[str, dict[str, Any]] = {}
        for template in TEMPLATES:
            sim_id = ids[f"{template}.py"]
            print(f"running {template} ...", flush=True)
            jobs[sim_id] = record_job(client, recorder, sim_id)
            print(f"  {jobs[sim_id]['snapshot_count']} live frames kept", flush=True)

        settings = recorder.get("/api/settings")
        recorder.get("/api/system")
        recorder.get("/api/templates")
        workspace_answer = recorder.get("/api/workspace")
        for row in workspace_answer["simulations"]:
            sim_id = row["id"]
            spec = recorder.get(f"/api/simulations/{sim_id}/spec")
            if spec["preview"]["grid"] is not None:
                for component in ("Ex", "Ey"):
                    recorder.get(f"/api/simulations/{sim_id}/permittivity", component=component)
            result_id = row["last_result_id"]
            assert result_id == jobs[sim_id]["result_id"], (result_id, jobs[sim_id])
            meta = recorder.get(f"/api/results/{result_id}")
            for monitor in meta["monitors"]:
                name = monitor["name"]
                if monitor["shape"] is None:
                    recorder.get(f"/api/results/{result_id}/spectra/{name}")
                    continue
                for component in monitor["components"]:
                    for quantity in QUANTITIES:
                        for index in range(len(monitor["wavelengths_um"])):
                            recorder.get(
                                f"/api/results/{result_id}/fields/{name}",
                                component=component,
                                quantity=quantity,
                                wavelength_index=index,
                            )
        manifest = {
            "version": 1,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "workspace": settings["workspace"],
            "responses": recorder.responses,
            "jobs": jobs,
        }
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    finally:
        state.jobs.shutdown()
        shutil.rmtree(root, ignore_errors=True)

    leaks = check_for_local_paths(OUT, home)
    if leaks:
        print("local paths left in:", *leaks, sep="\n  ", file=sys.stderr)
        return 1
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"wrote {len(recorder.responses)} answers to {OUT} ({total / 1e6:.1f} MB)")
    return 0


def check_for_local_paths(out: Path, home: str) -> list[str]:
    """Files whose text (JSON, or a binary answer's JSON header) still holds a local path."""
    user = Path(home).name
    pattern = re.compile(
        rb"[A-Za-z]:\\\\|[A-Za-z]:/|/home/|/Users/|" + re.escape(user.encode()), re.IGNORECASE
    )
    leaks = []
    for path in sorted(out.rglob("*.json")):
        if pattern.search(path.read_bytes()):
            leaks.append(str(path.relative_to(out)))
    for path in sorted(out.rglob("*.bin")):
        data = path.read_bytes()
        offset = 0
        while offset + 4 <= len(data):  # one array, or live frames back to back
            n = int.from_bytes(data[offset : offset + 4], "little")
            header = data[offset + 4 : offset + 4 + n]
            if pattern.search(header):
                leaks.append(str(path.relative_to(out)))
                break
            meta = json.loads(header)
            count = 1
            for size in meta["shape"]:
                count *= size
            offset += (4 + n + 3) // 4 * 4 + 4 * count
    return leaks


if __name__ == "__main__":
    sys.exit(main())
