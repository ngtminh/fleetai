"""Shared paths and ticket workflow. Product repos live in the code context file."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

TICKETS_DIR = ROOT / "tickets"
PDF_PATH = TICKETS_DIR / "list.pdf"
EMAIL_PATH = TICKETS_DIR / "email.desc.txt"
TICKETS_PATH = TICKETS_DIR / "unsolved_tickets.json"
CONTEXT_PATH = ROOT / "codebase" / "code-context.md"

UNRESOLVED = "unresolved"
VERIFYING = "verifying"
COMPLETED = "completed"
FIXED = "fixed"
TICKET_STATES = (UNRESOLVED, VERIFYING, COMPLETED, FIXED)
IN_FLIGHT = (VERIFYING, COMPLETED, FIXED)
READY = "ready"
BLOCKED = "blocked"
FAILED = "failed"

CURSOR_MODEL = (os.getenv("FLEETAI_CURSOR_MODEL") or "grok-4.6").strip()
GITHUB_REPO = os.getenv("FLEETAI_GITHUB_REPO") or "ngtminh/fleetai"


def cursor_api_key() -> str:
    return (os.getenv("CURSOR_API_KEY") or "").strip()

REQUIRED_TICKET_FIELDS = (
    "id",
    "title",
    "severity",
    "kind",
    "kind_reason",
    "services",
    "context",
    "expected",
)


def product_cwd() -> Path:
    raw = (os.getenv("FLEETAI_PRODUCT_ROOT") or "").strip()
    if not raw:
        raise RuntimeError("FLEETAI_PRODUCT_ROOT is required")
    root = Path(raw)
    if not root.is_dir():
        raise RuntimeError("product root is missing: {0}".format(root))
    return root


def code_context() -> str:
    if not CONTEXT_PATH.is_file():
        raise RuntimeError("missing code context: {0}".format(CONTEXT_PATH))
    text = CONTEXT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("code context is empty: {0}".format(CONTEXT_PATH))
    return text


def normalize_ticket(item: object) -> dict:
    if not isinstance(item, dict):
        raise RuntimeError("each ticket must be an object")
    missing = [name for name in REQUIRED_TICKET_FIELDS if name not in item]
    if missing:
        raise RuntimeError("ticket missing fields: {0}".format(", ".join(missing)))
    ticket_id = str(item["id"]).strip()
    if not ticket_id:
        raise RuntimeError("ticket id is empty")
    services = item.get("services") or []
    if not isinstance(services, list):
        raise RuntimeError("ticket {0}: services must be a list".format(ticket_id))
    ticket = dict(item)
    ticket["id"] = ticket_id
    ticket["services"] = [str(service).strip() for service in services if str(service).strip()]
    repos = item.get("repos")
    if repos is None:
        ticket["repos"] = []
    elif isinstance(repos, list):
        ticket["repos"] = repos
    else:
        raise RuntimeError("ticket {0}: repos must be a list".format(ticket_id))
    raw_status = ticket.get("status")
    report_status = ticket.get("report_status")
    if raw_status and not is_workflow_status(raw_status):
        if report_status is None:
            report_status = raw_status
        raw_status = ticket.get("state")
    ticket["report_status"] = str(report_status or "").strip()
    ticket["status"] = normalize_status(raw_status if raw_status is not None else ticket.get("state"))
    ticket.pop("state", None)
    return ticket


def normalize_tickets(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise RuntimeError("parser output must be a JSON array")
    tickets = []
    seen: set[str] = set()
    for item in raw:
        ticket = normalize_ticket(item)
        if ticket["id"] in seen:
            raise RuntimeError("duplicate ticket id: {0}".format(ticket["id"]))
        seen.add(ticket["id"])
        tickets.append(ticket)
    return tickets


def is_workflow_status(value: object) -> bool:
    return normalize_status(value, default=None) is not None


def normalize_status(value: object, default: str | None = UNRESOLVED) -> str | None:
    if value is None or value == "":
        return default
    text = str(value).strip()
    for allowed in TICKET_STATES:
        if text.lower() == allowed.lower():
            return allowed
    if default is None:
        return None
    raise RuntimeError(
        "ticket status must be unresolved, verifying, completed, or fixed: {0}".format(
            value
        )
    )


def last_verdict(text: str | None) -> str | None:
    if not text:
        return None
    allowed = {
        "verdict: fixed": FIXED,
        "verdict: failed": FAILED,
        "verdict: ready": READY,
        "verdict: blocked": BLOCKED,
    }
    for line in reversed(text.strip().splitlines()):
        cleaned = line.strip().strip("*").strip("`")
        found = allowed.get(cleaned.lower())
        if found:
            return found
    return None


def apply_workflow(tickets: list[dict], existing: list[dict]) -> list[dict]:
    previous = {item["id"]: item for item in existing}
    seen: set[str] = set()
    merged: list[dict] = []
    for ticket in tickets:
        prior = previous.get(ticket["id"])
        if prior and prior.get("status") in IN_FLIGHT:
            kept = dict(prior)
            if ticket.get("report_status"):
                kept["report_status"] = ticket["report_status"]
            merged.append(kept)
        else:
            if prior and not ticket.get("repos") and prior.get("repos"):
                ticket["repos"] = prior["repos"]
            ticket["status"] = UNRESOLVED
            merged.append(ticket)
        seen.add(ticket["id"])
    for prior in existing:
        if prior["id"] not in seen and prior.get("status") in IN_FLIGHT:
            merged.append(prior)
    return merged


def load_tickets(path: Path = TICKETS_PATH) -> list[dict]:
    if not path.is_file():
        return []
    return normalize_tickets(json.loads(path.read_text(encoding="utf-8")))


def save_tickets(tickets: list[dict], path: Path = TICKETS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tickets, indent=2) + "\n", encoding="utf-8")


def get_ticket(ticket_id: str, path: Path = TICKETS_PATH) -> dict | None:
    return next((item for item in load_tickets(path) if item["id"] == ticket_id), None)


def set_ticket_status(ticket_id: str, status: str, run_id: str | None = None) -> dict:
    status = normalize_status(status)
    tickets = load_tickets()
    ticket = next((item for item in tickets if item["id"] == ticket_id), None)
    if ticket is None:
        raise RuntimeError("ticket not found: {0}".format(ticket_id))
    ticket["status"] = status
    if run_id:
        ticket["solver_run_id"] = run_id
    save_tickets(tickets)
    return ticket


