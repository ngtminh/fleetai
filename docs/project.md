# fleetai

Reads a JarvisMD bug report and the evaluator email, asks Claude Sonnet on
Amazon Bedrock for the tickets that are still open, attaches local HBA
checkouts, then can hand one ticket to a local Cursor agent.

The product code is not in this repo. Paths and the service-to-repo map live
in `config.py`. Override the workspace with `FLEETAI_PRODUCT_ROOT` if needed.

## Commands

```bash
conda activate dev
cd /Users/minh/repos/netpalm.ai/fleetai

python main.py parse              # PDF + email -> tickets/unsolved_tickets.json
python main.py                    # list tickets and their state
python main.py JMD-30SEP-05       # solve one unresolved ticket
python main.py verify             # verify every verifying ticket
python main.py verify JMD-30SEP-05
python main.py complete JMD-30SEP-05
```

Each ticket stays in the same list. The parser writes `status: unresolved`.
The solver updates that same field:

- `unresolved` — parser default; solver may run it
- `verifying` — solver finished a run; another agent must check the fix
- `fixed` — verifier accepted the fix

`report_status` keeps the PDF label (`Open`, `Partially Fixed`).

## Files

- `config.py` — product root, ticket paths, service nicknames to checkouts
- `parser.py` — reads `tickets/list.pdf` and `tickets/email.desc.txt`, validates, attaches `repos`
- `prompts.py` — parser prompt. Placeholders are `{{email}}` and `{{report}}`
- `solver.py` — sends one ticket plus generated code context to a local Cursor agent
- `verified.py` — verifies a `verifying` ticket and sets `fixed` only on VERDICT: fixed
- `main.py` — parse, list, solve, verify, or complete
- `codebase/code-context.md` — generated product map used for inspection
- `tickets/unsolved_tickets.json` — ticket list with `repos` and `status`

## Environment

- `AWS_REGION` / `AWS_DEFAULT_REGION` and AWS credentials for the parser
- `BEDROCK_MODEL_ID` optional, defaults to Claude Sonnet 4.6
- `CURSOR_API_KEY` for the solver. Stored as a GitHub Actions secret on
  `ngtminh/fleetai`. GitHub will not return secret values to a local script.
  Local runs read the gitignored `.env`. Actions can inject
  `${{ secrets.CURSOR_API_KEY }}`.
- `FLEETAI_PRODUCT_ROOT` optional, defaults to `/Users/minh/repos/hba`
- `FLEETAI_CURSOR_MODEL` optional, defaults to `grok-4.6` with high + fast
