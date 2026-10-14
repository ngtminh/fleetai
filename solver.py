"""Send one unresolved ticket to a local Cursor agent in the product workspace."""

from __future__ import annotations

import json
import os
import sys

from config import (
    BLOCKED,
    COMPLETED,
    CURSOR_MODEL,
    READY,
    UNRESOLVED,
    VERIFYING,
    code_context,
    cursor_api_key,
    get_ticket,
    last_verdict,
    load_tickets,
    product_cwd,
    set_ticket_status,
)


def ticket_prompt(ticket: dict, context: str) -> str:
    return """
Fix this ticket completely.

This workspace is the product root, not the ticket runner. CODE CONTEXT names
the repositories, how they fit together, how to test, and any branch or
deploy rules. Follow that context. If it does not identify a repository for
this ticket, stop and say so.

Before editing:
- Read any handoff or rules the context names.
- Verify the reported cause from code, tests, or focused logs. Treat the
  ticket diagnosis as a hypothesis.
- Check the branch and existing uncommitted changes. Preserve them.

Make the smallest production-quality change that fixes the root cause. Follow
the existing architecture. Add a regression test. Run the focused tests and
builds the context describes. Do not commit, push, or deploy unless the user
separately authorized it.

After the happy path passes, check adjacent callers and the opposite case.
If a nearby path now breaks, fix that before you finish.

Finish with the verified cause, changed files, validation results, adjacent
checks, and any blocker. Then exactly one of these lines:
VERDICT: ready
VERDICT: blocked

Use ready only when the root cause is fixed and the focused tests passed.
Use blocked if the context does not name a repository, the branch is wrong,
or you could not complete the fix.

TICKET
{ticket}

CODE CONTEXT
{context}
""".strip().format(
        ticket=json.dumps(ticket, indent=2),
        context=context,
    )


def list_tickets() -> None:
    tickets = load_tickets()
    if not tickets:
        print("no tickets")
        return
    for ticket in tickets:
        repos = ", ".join(
            repo.get("name", "") for repo in ticket.get("repos") or [] if isinstance(repo, dict)
        )
        where = repos or ", ".join(ticket.get("services") or [])
        print("{0}\t{1}\t{2}\t{3}".format(
            ticket["id"], ticket["status"], where, ticket["title"]
        ))


def complete(ticket_id: str) -> None:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise SystemExit("ticket not found: {0}".format(ticket_id))
    if ticket["status"] != VERIFYING:
        raise SystemExit(
            "ticket {0} is {1}; complete only accepts verifying".format(
                ticket_id, ticket["status"]
            )
        )
    set_ticket_status(ticket_id, COMPLETED)
    print("{0}\t{1}".format(ticket_id, COMPLETED))


def solve(ticket_id: str) -> None:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise SystemExit("ticket not found: {0}".format(ticket_id))
    if ticket["status"] != UNRESOLVED:
        print("{0}\tskipped\t{1}".format(ticket_id, ticket["status"]))
        return

    api_key = cursor_api_key()
    if not api_key:
        raise SystemExit("CURSOR_API_KEY is required")

    from cursor_sdk import (
        Agent,
        AgentOptions,
        CursorAgentError,
        LocalAgentOptions,
        ModelParameterValue,
        ModelSelection,
    )

    model = CURSOR_MODEL
    if CURSOR_MODEL.startswith("grok-"):
        model = ModelSelection(
            id=CURSOR_MODEL,
            params=[
                ModelParameterValue(id="reasoning", value="high"),
                ModelParameterValue(id="fast", value="true"),
            ],
        )

    try:
        result = Agent.prompt(
            ticket_prompt(ticket, code_context()),
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(product_cwd())),
            ),
        )
    except CursorAgentError as err:
        raise RuntimeError("startup failed: {0}".format(err.message)) from err
    if result.status == "error":
        raise RuntimeError("run failed: {0}".format(result.id))

    if result.result:
        print(result.result)
    verdict = last_verdict(result.result)
    if verdict != READY:
        print("{0}\t{1}\t{2}".format(ticket_id, UNRESOLVED, verdict or BLOCKED))
        return

    set_ticket_status(ticket_id, VERIFYING, result.id)
    print("{0}\t{1}".format(ticket_id, VERIFYING))


def solve_all() -> None:
    tickets = [item for item in load_tickets() if item["status"] == UNRESOLVED]
    if not tickets:
        print("no unresolved tickets")
        return
    failed: list[str] = []
    for ticket in tickets:
        print("solving {0}".format(ticket["id"]), flush=True)
        try:
            solve(ticket["id"])
        except Exception as exc:
            print("{0}\tfailed\t{1}".format(ticket["id"], exc), file=sys.stderr)
            failed.append(ticket["id"])
    if failed:
        raise RuntimeError("failed: {0}".format(", ".join(failed)))


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if args == ["all"]:
        solve_all()
        return
    if len(args) != 1:
        raise SystemExit("usage: python solver.py <ticket-id>|all")
    solve(args[0])


if __name__ == "__main__":
    main()
