"""Send one unsolved ticket to a local Cursor agent in the HBA workspace."""

from __future__ import annotations

import json
import os
import sys

from config import (
    COMPLETED,
    CURSOR_MODEL,
    FIXED,
    UNRESOLVED,
    VERIFYING,
    code_context,
    cursor_api_key,
    get_ticket,
    load_tickets,
    product_cwd,
    set_ticket_status,
)


def ticket_prompt(ticket: dict, context: str) -> str:
    return """
Fix this ticket completely.

TICKET.repos lists the local checkouts. Open those first. CODE CONTEXT has
the rest of the product map. This runner repo is not the product code.

Before editing:
- Read the project handoff rule if it is available.
- Verify the reported cause from code, tests, or focused logs. Treat the
  ticket diagnosis as a hypothesis.
- Check the branch and existing uncommitted changes. Preserve them.

Make the smallest production-quality change that fixes the root cause. Follow
the existing architecture. Add a regression test. Run focused tests and the
relevant build or type check. Do not commit, push, or deploy unless the user
separately authorized it.

Finish with the verified cause, changed files, validation results, and any
blocker.

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
        repos = ", ".join(repo["name"] for repo in ticket["repos"])
        print("{0}\t{1}\t{2}\t{3}".format(
            ticket["id"], ticket["status"], repos, ticket["title"]
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
    set_ticket_status(ticket_id, FIXED)
    print("{0}\t{1}".format(ticket_id, FIXED))


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

    set_ticket_status(ticket_id, VERIFYING, result.id)
    print(result.status)
    print("{0}\t{1}".format(ticket_id, VERIFYING))
    if result.result:
        print(result.result)


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
