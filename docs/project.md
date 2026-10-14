# fleetai

Reads a bug report and the evaluator email, asks Claude Sonnet on Amazon
Bedrock for the tickets that are still open, then can hand each unresolved
ticket to a local Cursor agent.

The product code is not in this repo. `codebase/code-context.md` is the map:
repositories, how they fit together, tests, and branch rules. Set
`FLEETAI_PRODUCT_ROOT` to the folder that contains those checkouts.

## Commands

```bash
conda activate dev
cd /Users/minh/repos/netpalm.ai/fleetai

python main.py parse              # PDF + email -> tickets/unsolved_tickets.json
python main.py                    # list tickets and their state
python main.py run                # solve unresolved tickets, then verify them
python main.py JMD-30SEP-05       # solve one unresolved ticket
python main.py verify             # verify every verifying ticket
python main.py verify JMD-30SEP-05
python main.py complete JMD-30SEP-05
```

Each ticket stays in the same list. The parser writes new tickets as
`unresolved` and does not rewrite tickets that are already `verifying`,
`fixed`, or `completed`.

- `unresolved` — parser default; solver may run it; verifier fail returns here
- `verifying` — solver returned `VERDICT: ready`
- `fixed` — verifier returned `VERDICT: fixed`
- `completed` — `python main.py complete <id>` after live QA

`report_status` keeps the PDF label (`Open`, `Partially Fixed`).
`repos` is leftover metadata. Routing is `code-context.md` plus `services`.

## Files

- `config.py` — ticket paths and workflow. Reads the code context file.
- `parser.py` — reads `tickets/list.pdf` and `tickets/email.desc.txt`
- `prompts.py` — parser prompt. Placeholders are `{{email}}`, `{{report}}`, and `{{code_context}}`
- `solver.py` — sends one unresolved ticket plus the code context to a local Cursor agent, then sets `verifying` only on `VERDICT: ready`
- `verified.py` — sets `fixed` only on `VERDICT: fixed`; `VERDICT: failed` returns the ticket to `unresolved`
- `main.py` — parse, list, solve, run, verify, or complete
- `codebase/code-context.md` — product map supplied for the current codebase
- `tickets/unsolved_tickets.json` — ticket list with `status`

## Environment

- `AWS_REGION` / `AWS_DEFAULT_REGION` and AWS credentials for the parser
- `BEDROCK_MODEL_ID` optional, defaults to Claude Sonnet 4.6
- `CURSOR_API_KEY` for the solver. Stored as a GitHub Actions secret on
  `ngtminh/fleetai`. GitHub will not return secret values to a local script.
  Local runs read the gitignored `.env`. Actions can inject
  `${{ secrets.CURSOR_API_KEY }}`.
- `FLEETAI_PRODUCT_ROOT` required for solve and verify
- `FLEETAI_CURSOR_MODEL` optional, defaults to `grok-4.6` with high + fast
