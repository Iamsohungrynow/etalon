"""`import etalon` stays light: every public name loads on first use (plan-u1 §14.1).

SciPy and xarray load only when analysis or results are used; NumPy and the models
only when a name such as `et.Simulation` is.
"""

import json
import subprocess
import sys

HEAVY = ("scipy", "xarray", "pandas", "matplotlib", "cupy")


def _loaded_after(code: str) -> list[str]:
    """Heavy top-level packages in sys.modules after running `code` in a fresh interpreter."""
    probe = (
        f"import json, sys\n{code}\n"
        f"print(json.dumps(sorted({{m.split('.')[0] for m in sys.modules}} & set({HEAVY!r}))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=120
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_import_etalon_loads_no_scipy_or_xarray():
    assert _loaded_after("import etalon") == []


def test_building_a_simulation_loads_no_scipy_or_xarray():
    code = (
        "import etalon as et\n"
        "et.Simulation(size=(2, 2, 0), grid=et.UniformGrid(dl=0.1), run_time=1e-15,\n"
        "    sources=[et.PointSource(center=(0, 0, 0), component='Hz',\n"
        "        pulse=et.GaussianPulse(wavelength=1.55, bandwidth=0.2))])"
    )
    assert _loaded_after(code) == []


def test_lazy_names_still_resolve():
    import etalon as et

    assert callable(et.analysis.numerical_phase_velocity)
    assert et.SimulationResult.__name__ == "SimulationResult"
    from etalon import SimulationResult, analysis

    assert SimulationResult is et.SimulationResult
    assert analysis is et.analysis
    assert {"analysis", "SimulationResult"} <= set(dir(et))


def test_unknown_attribute_is_an_attribute_error():
    import etalon as et

    try:
        et.no_such_name  # noqa: B018
    except AttributeError as error:
        assert "no_such_name" in str(error)
    else:
        raise AssertionError("expected AttributeError")


def test_import_etalon_loads_no_numpy_or_core():
    """plan-u1 §14.1: every public name loads on first use, so `etalon studio` starts fast."""
    probe = (
        "import json, sys\nimport etalon\n"
        "print(json.dumps(sorted(m for m in sys.modules"
        " if m.split('.')[0] == 'numpy' or m.startswith('etalon.'))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=120
    )
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []


def test_every_public_name_resolves():
    import etalon as et

    for name in et.__all__:
        assert getattr(et, name) is not None, name
    namespace: dict[str, object] = {}
    exec("from etalon import *", namespace)
    assert set(et.__all__) <= set(namespace)
    assert set(et.__all__) <= set(dir(et))
    from etalon.core.simulation import Simulation

    assert et.Simulation is Simulation
