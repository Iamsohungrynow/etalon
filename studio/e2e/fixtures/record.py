"""Record the Results fixture: a real CPU run of phc_waveguide into the fixture workspace.

    .venv/Scripts/python studio/e2e/fixtures/record.py      (Windows)
    .venv/bin/python studio/e2e/fixtures/record.py          (POSIX)

It copies the template ``etalon/studio/templates/phc_waveguide.py`` into
``workspace/``, clears that script's sidecar, and runs it through Studio's own
job runner on the NumPy backend, exactly as ``POST /api/simulations/{id}/run``
would. The sidecar then holds ``status.json`` and one run folder with
``meta.json``, ``log.txt`` and ``result.npz`` (plane and point monitors at three
wavelengths, about 1.7 MB).

Rerun it only when the solver's output or Studio's run format changes; the
Playwright Results tests and tests/studio/test_results.py read the recording.
"""

import hashlib
import shutil
import sys
from pathlib import Path

from etalon.studio.jobs import JobManager
from etalon.studio.templates import TEMPLATE_DIR
from etalon.studio.workspace import sidecar_dir, simulation_id

WORKSPACE = Path(__file__).resolve().parent / "workspace"
NAME = "phc_waveguide.py"


def main() -> int:
    script = WORKSPACE / NAME
    shutil.copyfile(TEMPLATE_DIR / NAME, script)
    shutil.rmtree(sidecar_dir(script), ignore_errors=True)
    jobs = JobManager()
    job = jobs.start(
        script,
        WORKSPACE,
        simulation_id(NAME),
        hashlib.sha256(script.read_bytes()).hexdigest(),
        backend="numpy",
        device=None,
        live_snapshots=False,
    )
    print(f"recording {job.result_id} on the CPU ...", flush=True)
    jobs.wait(job)
    assert job.done is not None
    if job.done["status"] != "done":
        print(job.done, file=sys.stderr)
        return 1
    size = (job.run_dir / "result.npz").stat().st_size
    print(f"done: {job.run_dir.relative_to(WORKSPACE)} (result.npz {size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
