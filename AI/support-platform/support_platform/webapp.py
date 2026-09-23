"""Web dashboard for the support platform.

Standard library only (``http.server``) -- no Flask/FastAPI dependency.

Why a job queue instead of a plain request/response
---------------------------------------------------
A single triage takes 35-50 seconds on the local model. Holding an HTTP
connection open that long is fragile: browsers, proxies and fetch() timeouts all
interfere, and the page appears frozen with no feedback. So submitting a ticket
returns a ``job_id`` immediately and the browser polls for the result, which
also lets the UI show a live elapsed timer.

Routes
------
    GET  /                       dashboard page
    POST /api/tickets            {message, ticket_id?, customer} -> {job_id}
    GET  /api/jobs/<job_id>      job status / result
    GET  /api/tickets            queue rows + priority counts
    GET  /api/tickets/<id>       conversation, analyses and LLM attempts
    GET  /api/metrics            aggregate cost/latency metrics
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import Any
from urllib.parse import urlparse

from . import crm
from .config import settings
from .pipeline import SupportPipeline
from .storage import Database
from .trace import TraceCollector, use_collector

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 1_000_000  # refuse absurd payloads before reading them


class JobStore:
    """Tracks background triage jobs. Bounded so a long-lived server cannot
    grow without limit."""

    def __init__(self, limit: int = 200) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._limit = limit

    def create(self) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = {"status": "queued", "started": time.time()}
            self._order.append(job_id)
            while len(self._order) > self._limit:
                self._jobs.pop(self._order.pop(0), None)
        return job_id

    def update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


class Worker(threading.Thread):
    """Serialises triage jobs.

    One worker on purpose: the local model is the bottleneck and firing several
    concurrent 40-second generations at it makes every one of them slower. The
    queue position is surfaced in the UI instead.
    """

    def __init__(self, pipeline: SupportPipeline, jobs: JobStore) -> None:
        super().__init__(daemon=True)
        self.pipeline = pipeline
        self.jobs = jobs
        self.queue: Queue = Queue()

    def submit(self, job_id: str, payload: dict[str, Any]) -> None:
        self.queue.put((job_id, payload))

    def run(self) -> None:  # pragma: no cover - exercised manually
        while True:
            job_id, payload = self.queue.get()
            collector = TraceCollector()
            # Publish the collector immediately so polling can stream the trace
            # while the job is still running, not only once it finishes.
            self.jobs.update(job_id, status="running", started=time.time(), trace=collector)
            try:
                with use_collector(collector):
                    result = self.pipeline.process(
                        payload.get("message"),
                        ticket_id=payload.get("ticket_id") or None,
                        customer=payload.get("customer") or "web",
                    )
                self.jobs.update(job_id, status="done", result=result.as_dict())
            except Exception as exc:  # noqa: BLE001 - never kill the worker
                traceback.print_exc()
                self.jobs.update(
                    job_id, status="error", error=f"{type(exc).__name__}: {exc}"
                )
            finally:
                self.queue.task_done()


class Handler(BaseHTTPRequestHandler):
    server_version = "SupportPlatform/1.0"
    pipeline: SupportPipeline
    db: Database
    jobs: JobStore
    worker: Worker

    # -- helpers -------------------------------------------------------
    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"error": "not found"}, 404)
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("body must be a JSON object")
        return data

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quieter than the default one-line-per-request logging.
        if "/api/jobs/" not in (self.path or ""):
            print(f"  {self.command} {self.path}")

    # -- routing -------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path

        try:
            if route in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
            elif route.startswith("/static/"):
                name = route[len("/static/") :]
                # Prevent path traversal outside the static directory.
                target = (STATIC_DIR / name).resolve()
                if not str(target).startswith(str(STATIC_DIR.resolve())):
                    self._send_json({"error": "forbidden"}, 403)
                    return
                self._send_file(target)
            elif route == "/api/tickets":
                self._send_json(
                    {
                        "tickets": self.db.dashboard_rows(limit=100),
                        "counts": self.db.queue_counts(),
                        "actions": self.db.action_counts(),
                        "rules": self.db.rule_counts(),
                    }
                )
            elif route.startswith("/api/tickets/"):
                ticket_id = route[len("/api/tickets/") :]
                ticket = self.db.get_ticket(ticket_id)
                if not ticket:
                    self._send_json({"error": "ticket not found"}, 404)
                    return
                self._send_json(
                    {
                        "ticket": ticket,
                        "messages": self.db.get_messages(ticket_id),
                        "analyses": self.db.analyses_for(ticket_id),
                        "calls": self.db.ticket_calls(ticket_id),
                    }
                )
            elif route.startswith("/api/jobs/"):
                job = self.jobs.get(route[len("/api/jobs/") :])
                if not job:
                    self._send_json({"error": "job not found"}, 404)
                    return
                # Replace the live collector with a JSON-safe snapshot. Taken on
                # every poll, so the UI sees events as they happen rather than
                # only after the job completes.
                collector = job.pop("trace", None)
                job["trace"] = collector.snapshot() if collector is not None else []
                job["queue_depth"] = self.worker.queue.qsize()
                self._send_json(job)
            elif route == "/api/metrics":
                self._send_json(
                    {
                        "metrics": self.db.metrics_summary(),
                        "model": settings.model,
                        "api_base": settings.api_base,
                    }
                )
            elif route == "/api/identities":
                # Stands in for a login. In production the identity would come
                # from the authenticated session and this endpoint would not
                # exist -- a customer must never get to choose who they are.
                self._send_json(
                    {
                        "identities": [
                            {
                                "customer_id": c["customer_id"],
                                "name": c["name"],
                                "email": c["email"],
                                "plan": c["plan"],
                            }
                            for c in crm.list_customers()
                        ]
                    }
                )
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        try:
            if route != "/api/tickets":
                self._send_json({"error": "not found"}, 404)
                return

            payload = self._read_json()
            # Note: we do NOT reject an empty message here. Bad input is a
            # first-class case the pipeline reports on, so it should flow
            # through the same path and appear in the queue like any ticket.
            job_id = self.jobs.create()
            self.worker.submit(job_id, payload)
            self._send_json(
                {"job_id": job_id, "queue_depth": self.worker.queue.qsize()}, 202
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    db = Database()
    pipeline = SupportPipeline(db=db)
    jobs = JobStore()
    worker = Worker(pipeline, jobs)
    worker.start()

    Handler.pipeline = pipeline
    Handler.db = db
    Handler.jobs = jobs
    Handler.worker = worker

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"\n  Support dashboard  ->  http://{host}:{port}")
    print(f"  model              :  {settings.model} @ {settings.api_base}")
    print(f"  database           :  {settings.db_path}")
    print("  Ctrl-C to stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopping...")
    finally:
        httpd.server_close()
