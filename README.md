# fleetai

Parse a bug report into tickets, then send each unresolved ticket to a local
Cursor agent. The product repos and how to work in them are in
`codebase/code-context.md`. Set `FLEETAI_PRODUCT_ROOT` to the folder that
contains those checkouts.

```bash
conda activate dev
python main.py parse
python main.py
python main.py JMD-30SEP-05
python main.py verify
python main.py complete JMD-30SEP-05   # live QA only; sets completed, not fixed
```

See `docs/project.md`.
