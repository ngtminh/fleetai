"""Verify tickets in verifying status. A pass updates status to fixed."""

from __future__ import annotations

import json
import sys

from config import (
    CURSOR_MODEL,
    FAILED,
    FIXED,
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


def verify_prompt(ticket: dict, context: str) -> str:
    return """
Verify this ticket. Do not implement a new fix. Do not commit, push, or deploy.

This workspace is the product root, not the ticket runner. CODE CONTEXT names
the repositories and how to test them. Follow that context.

Verification method:
1. Read TICKET.expected. That is the acceptance bar.
2. Confirm the current code path implements that behaviour. Treat the ticket
   diagnosis as a hypothesis.
3. Run the focused tests the context describes for this change.
4. Check the branch and existing uncommitted changes. Preserve them.
5. Check adjacent callers and the opposite case.
6. Do not mark the ticket fixed from a live environment check unless that
   check was actually run. Local code plus passing focused tests is enough
   only when step 5 is also clean.

Pass only if expected, code, and focused tests agree and the change does
not introduce a new bug. Otherwise fail so the ticket returns to unresolved.

Finish with the evidence (files, tests, what you could not check) and then
exactly one of these lines:
VERDICT: fixed
VERDICT: failed

TICKET
{ticket}

CODE CONTEXT
{context}
""".strip().format(
        ticket=json.dumps(ticket, indent=2),
        context=context,
    )


def verify(ticket_id: str) -> None:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise SystemExit("ticket not found: {0}".format(ticket_id))
    if ticket["status"] != VERIFYING:
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
            verify_prompt(ticket, code_context()),
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
    if verdict == FIXED:
        set_ticket_status(ticket_id, FIXED, result.id)
        print("{0}\t{1}".format(ticket_id, FIXED))
        return
    if verdict == FAILED:
        set_ticket_status(ticket_id, UNRESOLVED, result.id)
        print("{0}\t{1}\t{2}".format(ticket_id, UNRESOLVED, FAILED))
        return
    print("{0}\t{1}\t{2}".format(ticket_id, VERIFYING, verdict or "no verdict"))


def verify_all() -> None:
    tickets = [item for item in load_tickets() if item["status"] == VERIFYING]
    if not tickets:
        print("no verifying tickets")
        return
    failed: list[str] = []
    for ticket in tickets:
        print("verifying {0}".format(ticket["id"]), flush=True)
        try:
            verify(ticket["id"])
        except Exception as exc:
            print("{0}\tfailed\t{1}".format(ticket["id"], exc), file=sys.stderr)
            failed.append(ticket["id"])
    if failed:
        raise RuntimeError("failed: {0}".format(", ".join(failed)))


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if not args or args == ["all"]:
        verify_all()
        return
    if len(args) != 1:
        raise SystemExit("usage: python verified.py [<ticket-id>|all]")
    verify(args[0])


if __name__ == "__main__":
    main()
