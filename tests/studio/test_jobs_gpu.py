"""A template on the GPU through Studio's runner: energy and snapshots computed on the device."""

import pytest

cp = pytest.importorskip("cupy")

from tests.studio.conftest import make_client, make_state  # noqa: E402
from tests.studio.test_jobs import collect, messages  # noqa: E402

pytestmark = pytest.mark.gpu


@pytest.fixture
def gpu_client(workspace, config_dir):
    try:
        if cp.cuda.runtime.getDeviceCount() == 0:
            pytest.skip("no CUDA device")
    except cp.cuda.runtime.CUDARuntimeError:
        pytest.skip("no CUDA driver")
    state = make_state(workspace, config_dir)
    state.settings.put(state.settings.get().model_copy(update={"backend": "cuda:0"}))
    yield make_client(state)
    state.jobs.shutdown()


def test_strip_template_on_the_gpu_snapshots_by_default(gpu_client):
    row = gpu_client.post(
        "/api/simulations", json={"template": "strip_waveguide", "name": "strip"}
    ).json()
    job = gpu_client.post(f"/api/simulations/{row['id']}/run").json()
    frames = collect(gpu_client, job["job_id"])
    (started,) = messages(frames, "started")
    assert started["backend"] == "cuda:0"
    assert started["snapshots"] is True  # Settings live_snapshots is off: the GPU default
    (done,) = messages(frames, "done")
    assert done["status"] == "done", done
    energy = [m["energy"] for m in messages(frames, "progress")]
    assert max(energy) > 0
    snapshots = [m for _, m in frames if isinstance(m, tuple)]
    assert snapshots and all(h["shape"] == [256, 156] for h, _ in snapshots)
    meta = gpu_client.get(f"/api/results/{job['result_id']}").json()
    assert meta["backend"] == "cuda:0" and meta["device"]
