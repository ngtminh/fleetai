"""Shared paths and the ticket-service to checkout map."""

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

PRODUCT_ROOT = Path(os.getenv("FLEETAI_PRODUCT_ROOT") or "/Users/minh/repos/hba")
HANDOFF_RULE = PRODUCT_ROOT / ".cursor" / "rules" / "hba-platform-handoff.mdc"
SSH_CONFIG = Path.home() / ".ssh" / "config"

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

REPOS = {
    "jmd-frontend": {
        "remote": "cto-hba/jmd-frontend",
        "owns": "React/Vite SPA. Regional URLs and flags: public/server-profiles.json",
    },
    "jarvismd-backend": {
        "remote": "cto-hba/jarvismd-backend",
        "owns": "FastAPI session APIs, annotation, Summary, SNOMED proxy, GP apply audit",
    },
    "transcribe": {
        "remote": "cto-hba/transcribe",
        "owns": "Socket.IO STT. App is transcribe/backend",
    },
    "nlp-services": {
        "remote": "healthbridge-inc/nlp-services",
        "owns": "Celery NLP worker for speaker annotation and Summary generation",
    },
    "jmd-gp-consult-template": {
        "remote": "healthbridge-inc/jmd-gp-consult-template",
        "owns": "GP template UI + extract API. Vendor into jmd-frontend after UI changes",
    },
    "snomed": {
        "remote": "cto-hba/snomed",
        "owns": "SNOMED coding service on its own VM. Browser must not call it",
    },
    "ask-jarvismd": {
        "remote": "healthbridge-inc/ask-jarvismd",
        "owns": "Ask JarvisMD chatbot",
    },
    "credit-manager": {
        "remote": "healthbridge-inc/credit-manager",
        "owns": "Internal credit API",
    },
    "jmd-xycare": {
        "remote": "healthbridge-inc/jmd-xycare",
        "owns": "Local XYClient/SystmOne probes, not the hosted app",
    },
    "jmd-world-dashboard": {
        "remote": "healthbridge-inc/jmd-world-dashboard",
        "owns": "Fleet dashboard",
    },
    "healthbridge-homepage": {
        "remote": "cto-hba/healthbridge-homepage",
        "owns": "HBA public website",
    },
    "jmd-templates": {
        "remote": "cto-hba/jmd-templates",
        "owns": "Template source notes. Not the packaged GP module",
    },
}

# Parser service nicknames -> child repos under PRODUCT_ROOT.
SERVICE_REPOS = {
    "page load": ["jmd-frontend"],
    "session activity": ["jmd-frontend"],
    "annotated transcript ui": ["jmd-frontend"],
    "copy icon": ["jmd-frontend"],
    "timestamps": ["jmd-frontend"],
    "survey": ["jmd-frontend"],
    "uk time": ["jmd-frontend"],
    "annotated transcript": ["jarvismd-backend", "nlp-services", "jmd-frontend"],
    "clinical summary": ["jarvismd-backend", "nlp-services", "jmd-frontend"],
    "save & complete": ["jarvismd-backend", "jmd-frontend"],
    "transcription": ["transcribe", "jmd-frontend"],
    "live transcript": ["transcribe", "jmd-frontend"],
    "recording gaps": ["transcribe", "jarvismd-backend"],
    "gp consult template": ["jmd-gp-consult-template", "jmd-frontend"],
    "snomed-ct coder": ["snomed", "jarvismd-backend", "jmd-frontend"],
    "snomed": ["snomed", "jarvismd-backend", "jmd-frontend"],
    "chatbot": ["ask-jarvismd"],
    "credits": ["credit-manager"],
    "fhir": ["jarvismd-backend", "jmd-xycare"],
    "systmone": ["jarvismd-backend", "jmd-xycare"],
}


def repo_path(name: str) -> Path:
    return PRODUCT_ROOT / name


def product_cwd() -> Path:
    if PRODUCT_ROOT.is_dir():
        return PRODUCT_ROOT
    raise RuntimeError(
        "product root is missing: {0}. Set FLEETAI_PRODUCT_ROOT.".format(PRODUCT_ROOT)
    )


def repos_for_services(services: list[str]) -> list[dict]:
    names: list[str] = []
    for service in services:
        for name in SERVICE_REPOS.get(service.strip().lower(), ()):
            if name not in names:
                names.append(name)
    if not names:
        names.append("jmd-frontend")
    return [
        {
            "name": name,
            "path": str(repo_path(name)),
            "remote": REPOS[name]["remote"],
        }
        for name in names
        if name in REPOS
    ]


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
    ticket["repos"] = repos_for_services(ticket["services"])
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
        "ticket status must be unresolved, verifying, or completed: {0}".format(value)
    )


def apply_workflow(tickets: list[dict], existing: list[dict]) -> list[dict]:
    previous = {item["id"]: item for item in existing}
    for ticket in tickets:
        prior = previous.get(ticket["id"])
        if prior and prior.get("status") in (VERIFYING, COMPLETED, FIXED):
            ticket["status"] = prior["status"]
            if prior.get("solver_run_id"):
                ticket["solver_run_id"] = prior["solver_run_id"]
        else:
            ticket["status"] = UNRESOLVED
    return tickets


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


def code_context() -> str:
    root = PRODUCT_ROOT
    rows = [
        (
            "page load, session activity, annotated transcript UI, copy icon, timestamps, survey, UK time",
            "jmd-frontend",
        ),
        (
            "annotated transcript pipeline, clinical summary persistence, Save & complete, evaluation snapshots",
            "jarvismd-backend",
        ),
        ("transcription, live transcript, recording gaps, resume/audio", "transcribe"),
        ("speaker annotation LLM, Summary generation", "nlp-services"),
        ("GP consult template", "jmd-gp-consult-template"),
        ("SNOMED-CT coder", "snomed"),
        ("chatbot", "ask-jarvismd"),
        ("credits", "credit-manager"),
        ("FHIR / SystmOne local probe", "jmd-xycare"),
        ("world dashboard", "jmd-world-dashboard"),
        ("public site", "healthbridge-homepage"),
        ("template source notes", "jmd-templates"),
    ]
    table = [
        "| {0} | `{1}` | `{2}` | {3} |".format(
            services,
            repo_path(name),
            REPOS[name]["remote"],
            REPOS[name]["owns"],
        )
        for services, name in rows
    ]
    return "\n".join(
        [
            "# JarvisMD / HBA product code",
            "",
            "This FleetAI repo is the ticket runner only. Product code lives under",
            "`{0}`. That folder is a container of independent Git".format(root),
            "repositories. Run Git commands inside the child repo you are changing.",
            "",
            "Read `{0}` first.".format(HANDOFF_RULE),
            "",
            "SSH aliases are in `{0}`. Use `ssh <alias>`. Do not".format(SSH_CONFIG),
            "copy keys or edit that file unless the user asks.",
            "",
            "## Repositories",
            "",
            "| Ticket service names | Local checkout | Remote | Owns |",
            "|---|---|---|---|",
            *table,
            "",
            "## How a consult flows",
            "",
            "`browser mic -> transcribe Socket.IO -> transcript Mongo -> backend normalize -> NLP annotation -> annotated transcript -> Summary -> SNOMED suggestions -> clinician edits -> Save & complete`",
            "",
            "If live text is present and annotated text is missing, start in",
            "`jarvismd-backend` annotation code, not the coder.",
            "If a GP template UI change is needed, edit `jmd-gp-consult-template`, then",
            "`npm run vendor:gp-consult-templates -- ../jmd-gp-consult-template` in",
            "`jmd-frontend`. Changing the template repo alone does not update the SPA.",
            "",
            "## UK evaluation target",
            "",
            '"UK" means `https://jarvismd-trial.xycare.co.uk`, not the older HBA UK VM.',
            "",
            "| Role | SSH alias |",
            "|---|---|",
            "| UK deploy / runtime | `staging-uk-jmd-xycare-cicd` |",
            "| UK VM admin | `staging-uk-jmd-xycare-admin` |",
            "| Older HBA UK VM | `prod-uk-jmd` |",
            "| SNOMED host | `snomed-uk` |",
            "| Dev JarvisMD VM | `dev-javismd` |",
            "| AU / SG / KH / MX / CA | `prod-au-cicd`, `prod-sg-cicd`, `prod-kh`, `prod-mex-cicd`, `prod-canada-cicd` |",
            "",
            "Frontend profile `uk-xycare` points REST and `/transcribe` at the Xycare origin.",
            "",
            "## Work rules for the solver",
            "",
            "- Prefer the local checkout over cloning the remote.",
            "- Check `git status --short --branch` in each affected child repo first.",
            "- Keep existing uncommitted work. Do not switch branches.",
            "- Do not commit, push, or deploy unless the user authorized it.",
            "- Backend UK CI deploys from `staging/uk-xycare`. `prod/uk` is a no-op in CI.",
            "- Frontend `main` does not auto-deploy to the Xycare UK container.",
            "",
        ]
    )
