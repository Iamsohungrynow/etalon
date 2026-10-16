"""Jobs: one ``multiprocessing`` spawn child per run, and what the server keeps of it.

The child (``runner.run_job``) steps the solver and sends JSON messages and
binary snapshots through a queue. A reader thread here keeps the history
(``started``, every ``progress``, the last 500 log lines, the last snapshot,
``done``) and forwards each message to the WebSocket subscribers. A GPU crash
kills only the child; the reader then finishes the run as failed.

Cancel sets an event the child checks every 50 ms; the child saves its partial
DFT data and stops. If it has not stopped after ``CANCEL_GRACE_S`` (it is busy
outside the stepping loop), it is terminated.
"""

import asyncio
import atexit
import contextlib
import json
import multiprocessing
import queue as queue_module
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etalon.studio.runner import run_job, write_json_atomically
from etalon.studio.workspace import STATUS_FILE, read_sidecar_status, sidecar_dir

CANCEL_GRACE_S = 1.5
LOG_HISTORY = 500
SNAPSHOT_BACKLOG = 4
"""A subscriber more than this many snapshots behind skips the next ones."""

Message = dict[str, Any] | bytes


def run_stamp(now: datetime | None = None) -> str:
    """``20261016T140203Z``: the run folder's name and the second half of the result id."""
    return (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


class Subscriber:
    """One WebSocket's queue, fed from the reader thread through its event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.queue: asyncio.Queue[Message] = asyncio.Queue()
        self.ready = False
        """False until ``started`` (or ``done``) has been replayed to it."""

    def push(self, message: Message) -> None:
        if isinstance(message, bytes) and self.queue.qsize() > SNAPSHOT_BACKLOG:
            return
        with contextlib.suppress(RuntimeError):  # the loop has closed
            self.loop.call_soon_threadsafe(self.queue.put_nowait, message)


@dataclass
class Job:
    job_id: str
    sim_id: str
    result_id: str
    run_dir: Path
    status_path: Path
    started_at: str
    process: Any = None
    messages: Any = None
    cancel_event: Any = None
    started: dict[str, Any] | None = None
    progress: list[dict[str, Any]] = field(default_factory=list)
    log: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=LOG_HISTORY))
    snapshot: bytes | None = None
    done: dict[str, Any] | None = None
    cancel_requested_at: float | None = None
    subscribers: list[Subscriber] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    finished: threading.Event = field(default_factory=threading.Event)

    @property
    def running(self) -> bool:
        return self.done is None

    def _history(self) -> dict[str, Any]:
        return {"type": "history", "progress": list(self.progress), "log": list(self.log)}

    def _replay(self) -> list[Message]:
        replay: list[Message] = []
        if self.started is not None:
            replay.append(self.started)
        replay.append(self._history())
        if self.snapshot is not None:
            replay.append(self.snapshot)
        if self.done is not None:
            replay.append(self.done)
        return replay

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> Subscriber:
        """A subscriber that gets ``started``, ``history``, then live messages (§13.3)."""
        subscriber = Subscriber(loop)
        with self.lock:
            if self.started is not None or self.done is not None:
                subscriber.ready = True
                for message in self._replay():
                    subscriber.push(message)
            self.subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self.lock, contextlib.suppress(ValueError):
            self.subscribers.remove(subscriber)

    def dispatch(self, message: Message) -> None:
        """Record a message from the child and forward it (reader thread)."""
        with self.lock:
            if isinstance(message, bytes):
                self.snapshot = message
            elif message["type"] == "started":
                self.started = message
            elif message["type"] == "progress":
                self.progress.append(message)
            elif message["type"] == "log":
                self.log.append(message)
            elif message["type"] == "done":
                self.done = message
            for subscriber in self.subscribers:
                if subscriber.ready:
                    subscriber.push(message)
                elif self.started is not None or self.done is not None:
                    # The first started (or a done without one) releases waiting subscribers.
                    subscriber.ready = True
                    for replayed in self._replay():
                        subscriber.push(replayed)


class JobManager:
    """The jobs of one Studio server; at most one running job per simulation."""

    def __init__(self, on_finished: Callable[[Job], None] | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._on_finished = on_finished
        self._context = multiprocessing.get_context("spawn")
        atexit.register(self.shutdown)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def running_for(self, sim_id: str) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.sim_id == sim_id and job.running:
                    return job
        return None

    def running(self) -> dict[str, str]:
        """Simulation id → job id of every running job."""
        with self._lock:
            return {job.sim_id: job.job_id for job in self._jobs.values() if job.running}

    def by_result(self, result_id: str) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.result_id == result_id:
                    return job
        return None

    def start(
        self,
        script: Path,
        workspace: Path,
        sim_id: str,
        script_sha256: str,
        backend: str | None,
        device: int | None,
        live_snapshots: bool,
    ) -> Job:
        """Start a run of ``script``; the caller has checked nothing else runs it."""
        sidecar = sidecar_dir(script)
        now = datetime.now(UTC)
        stamp = run_stamp(now)
        runs = sidecar / "runs"
        suffix = 1
        while (runs / stamp).exists():
            suffix += 1
            stamp = f"{run_stamp(now)}-{suffix}"
        run_dir = runs / stamp
        run_dir.mkdir(parents=True)
        previous = read_sidecar_status(script)
        job = Job(
            job_id=secrets.token_hex(8),
            sim_id=sim_id,
            result_id=f"{sim_id}~{stamp}",
            run_dir=run_dir,
            status_path=sidecar / STATUS_FILE,
            started_at=now.isoformat(),
        )
        params = {
            "script": str(script.resolve()),
            "workspace": str(workspace.resolve()),
            "run_dir": str(run_dir.resolve()),
            "status_path": str(job.status_path.resolve()),
            "sim_id": sim_id,
            "result_id": job.result_id,
            "stamp": stamp,
            "started_at": job.started_at,
            "script_sha256": script_sha256,
            "previous_result": None if previous is None else previous.last_result,
            "backend": backend,
            "device": device,
            "live_snapshots": live_snapshots,
        }
        write_json_atomically(
            job.status_path,
            {
                "status": "running",
                "started_at": job.started_at,
                "script_sha256": script_sha256,
                "last_run": stamp,
                "last_result": params["previous_result"],
                "heartbeat_at": now.isoformat(),
            },
        )
        job.messages = self._context.Queue()
        job.cancel_event = self._context.Event()
        job.process = self._context.Process(
            target=run_job,
            args=(params, job.messages, job.cancel_event),
            name=f"etalon-job-{job.job_id}",
        )
        with self._lock:
            self._jobs[job.job_id] = job
        try:
            job.process.start()
        except BaseException:
            with self._lock:
                del self._jobs[job.job_id]
            raise
        threading.Thread(
            target=self._read, args=(job,), name=f"etalon-job-reader-{job.job_id}", daemon=True
        ).start()
        return job

    def cancel(self, job: Job) -> None:
        with job.lock:
            if job.cancel_requested_at is None:
                job.cancel_requested_at = time.monotonic()
        job.cancel_event.set()

    def _read(self, job: Job) -> None:
        while True:
            try:
                message = job.messages.get(timeout=0.2)
            except queue_module.Empty:
                if not job.process.is_alive():
                    break
                requested = job.cancel_requested_at
                if requested is not None and time.monotonic() - requested > CANCEL_GRACE_S:
                    job.process.terminate()
                continue
            except (EOFError, OSError):
                break
            job.dispatch(message)
            if isinstance(message, dict) and message["type"] == "done":
                break
        job.process.join(timeout=10)
        if job.done is None:
            self._finish_lost(job)
        job.finished.set()
        if self._on_finished is not None:
            with contextlib.suppress(Exception):
                self._on_finished(job)

    def _finish_lost(self, job: Job) -> None:
        """The child ended without ``done``: killed after a cancel, or it crashed."""
        cancelled = job.cancel_requested_at is not None
        status = "cancelled" if cancelled else "failed"
        code = job.process.exitcode
        error = None
        if not cancelled:
            error = {
                "message": f"the run process exited with code {code}",
                "traceback": "",
                "line": None,
            }
        has_result = (job.run_dir / "result.npz").exists()
        finished_at = datetime.now(UTC).isoformat()
        meta_path = job.run_dir / "meta.json"
        meta: dict[str, Any] = {}
        if meta_path.exists():
            with contextlib.suppress(OSError, ValueError):
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(
            {
                "result_id": job.result_id,
                "simulation_id": job.sim_id,
                "status": status,
                "started_at": job.started_at,
                "finished_at": finished_at,
                "has_result": has_result and bool(meta.get("has_result")),
                "error": error,
                "suggestion": None,
            }
        )
        with contextlib.suppress(OSError):
            write_json_atomically(meta_path, meta)
        with contextlib.suppress(OSError, ValueError):
            status_json = json.loads(job.status_path.read_text(encoding="utf-8"))
            status_json.update({"status": status, "finished_at": finished_at, "eta_s": None})
            write_json_atomically(job.status_path, status_json)
        job.dispatch(
            {
                "type": "done",
                "status": status,
                "result_id": job.result_id if meta["has_result"] else None,
                "error": error,
                "suggestion": None,
            }
        )

    def wait(self, job: Job, timeout: float | None = None) -> bool:
        """Block until the job has finished (tests, shutdown)."""
        return job.finished.wait(timeout)

    def shutdown(self) -> None:
        """Cancel every running job, and terminate the ones that do not stop."""
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.running]
        for job in jobs:
            self.cancel(job)
        deadline = time.monotonic() + CANCEL_GRACE_S + 1.0
        for job in jobs:
            job.process.join(timeout=max(0.0, deadline - time.monotonic()))
            if job.process.is_alive():
                job.process.terminate()
