"""Parse the report, list open tickets, or send one ticket to the solver."""

from __future__ import annotations

import sys

import solver


def main() -> None:
    args = sys.argv[1:]
    if not args or args == ["list"]:
        solver.list_tickets()
        return
    if args == ["parse"]:
        import parser

        parser.main()
        return
    if args == ["solve"] or args == ["all"]:
        solver.solve_all()
        return
    if args == ["run"]:
        solver.solve_all()
        import verified

        verified.verify_all()
        return
    if args[0] == "solve" and len(args) == 2:
        solver.solve(args[1])
        return
    if args == ["verify"]:
        import verified

        verified.verify_all()
        return
    if args[0] == "verify" and len(args) == 2:
        import verified

        verified.verify(args[1])
        return
    if args[0] == "complete" and len(args) == 2:
        solver.complete(args[1])
        return
    if len(args) == 1:
        solver.solve(args[0])
        return
    raise SystemExit(
        "usage: python main.py [parse|list|solve|run|solve <ticket-id>|verify|verify <ticket-id>|complete <ticket-id>|<ticket-id>]"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
