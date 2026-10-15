"""Throughput (plan-m0 G6): prints cell-updates/s, never fails. Run with -s to see it.

M0 target: ≥ 2e8 cell-updates/s on a 2000 × 2000 grid on an RTX 3060-class GPU.
"""

import pytest

from etalon.validation.throughput import measure_throughput


def _report(t):
    print(
        f"\n{t.backend} [{t.precision}] {t.device}: {t.cells[0]} x {t.cells[1]} cells, "
        f"{t.steps} steps in {t.wall_time_s:.2f} s -> {t.cell_updates_per_s:.3g} cell-updates/s"
    )


def test_g6_numpy_reference_throughput():
    _report(measure_throughput(region_cells=500, steps=50, backend="numpy"))


@pytest.mark.gpu
@pytest.mark.parametrize("precision", ["single", "double"])
def test_g6_cuda_throughput(precision):
    pytest.importorskip("cupy")
    _report(measure_throughput(region_cells=2000, steps=500, backend="cuda", precision=precision))
