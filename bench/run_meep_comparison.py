"""Run the etalon-vs-Meep benchmark: Meep (subprocess, cached) → etalon → report.

    python -m bench.run_meep_comparison                      # 2D tier, every device
    python -m bench.run_meep_comparison --tier 3d --devices straight bend
    python -m bench.run_meep_comparison --skip-meep          # report on existing Meep results

Meep (GPL) runs only as a subprocess in its own conda environment (bench/meep/env.yaml);
nothing here imports it. Runners:

* ``wsl`` (default on Windows): inside the WSL2 distribution set up for the bench,
  ``wsl.exe -d Ubuntu-24.04 -u root --cd <repo> -- micromamba run ... mpirun -np N ...``
* ``native`` (a Linux box): the same command without the ``wsl.exe`` prefix.

A Meep result is reused while its config hash and code hash match the current files: Meep
references depend on neither etalon nor its git sha. ``--force-meep`` re-runs them. The
etalon side then runs per device in a subprocess (``bench.etalon.run_device``), and
``bench.report`` writes bench/results/<sha>.md and the "meep_comparison" section of
bench/results/<sha>.json, and prints the table.
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

if __package__ in (None, ""):  # run as a file: python bench/run_meep_comparison.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import BenchConfig, load_config
from bench.record import REPO, git_sha
from bench.report import write_report
from bench.schema import BENCH, code_sha256, out_path, read_result

CacheState = Literal["missing", "stale", "fresh"]


@dataclass(frozen=True)
class MeepRunner:
    """How to start a process in the Meep environment."""

    kind: Literal["wsl", "native"]
    processes: int
    distro: str = "Ubuntu-24.04"
    micromamba: str = "/usr/local/bin/micromamba"
    root_prefix: str = "/opt/micromamba"
    env: str = "etalon-meep"

    def command(self, device: str, tier: str, extra: list[str], repo: Path = REPO) -> list[str]:
        inner = [
            self.micromamba, "run", "-r", self.root_prefix, "-n", self.env,
            "mpirun", "-np", str(self.processes),
            "python", "-m", "mpi4py", "-m", "bench.meep.run_device", device, "--tier", tier,
            *extra,
        ]  # fmt: skip
        if self.kind == "wsl":
            return ["wsl.exe", "-d", self.distro, "-u", "root", "--cd", str(repo), "--", *inner]
        return inner


def meep_cache_state(cfg: BenchConfig, tier: str, device: str, root: Path = BENCH) -> CacheState:
    """Whether bench/meep/out/<tier>/<device>.json matches the current config and Meep code."""
    path = out_path("meep", tier, device, root)
    if not path.exists():
        return "missing"
    result = read_result(path)
    current = result.config_sha256 == cfg.config_sha256(tier, device)
    if not current or result.code_sha256 != code_sha256(root=root):
        return "stale"
    return "fresh"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tier", default="2d")
    parser.add_argument("--devices", nargs="*", help="default: every device of the tier")
    parser.add_argument(
        "--runner",
        choices=("wsl", "native"),
        default="wsl" if sys.platform == "win32" else "native",
    )
    parser.add_argument("--distro", default="Ubuntu-24.04", help="WSL distribution")
    parser.add_argument("--micromamba", default=None, help="micromamba executable")
    parser.add_argument("--root-prefix", default="/opt/micromamba")
    parser.add_argument("--env", default="etalon-meep")
    parser.add_argument(
        "--np", type=int, default=None, help="Meep MPI ranks (config: meep.processes)"
    )
    parser.add_argument("--backends", default="cuda,numpy")
    parser.add_argument("--force-meep", action="store_true", help="re-run cached Meep results")
    parser.add_argument("--skip-meep", action="store_true")
    parser.add_argument("--skip-etalon", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config()
    tier = cfg.tier(args.tier)
    devices = args.devices or list(tier.devices)
    unknown = [d for d in devices if d not in tier.devices]
    if unknown:
        raise SystemExit(f"not in tier {args.tier!r}: {', '.join(unknown)}")
    runner = MeepRunner(
        kind=args.runner,
        processes=args.np or cfg.meep.processes,
        distro=args.distro,
        micromamba=args.micromamba
        or ("/usr/local/bin/micromamba" if args.runner == "wsl" else "micromamba"),
        root_prefix=args.root_prefix,
        env=args.env,
    )
    sha = git_sha()
    for device in devices:
        if not args.skip_meep:
            state = meep_cache_state(cfg, args.tier, device)
            if state == "fresh" and not args.force_meep:
                print(f"meep {device} {args.tier}: cached result is current")
            else:
                command = runner.command(device, args.tier, ["--git-sha", sha])
                print(f"meep {device} {args.tier} ({state}): {' '.join(command)}", flush=True)
                started = time.perf_counter()
                cwd = REPO if runner.kind == "native" else None
                subprocess.run(command, check=True, cwd=cwd)
                print(f"  done in {time.perf_counter() - started:.0f} s", flush=True)
        if not args.skip_etalon:
            command = [
                sys.executable, "-m", "bench.etalon.run_device", device,
                "--tier", args.tier, "--backends", args.backends,
            ]  # fmt: skip
            subprocess.run(command, check=True, cwd=REPO)

    path = write_report(cfg, [args.tier], sha)
    print(path.read_text(encoding="utf-8"))
    print(f"wrote {path} and {path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
