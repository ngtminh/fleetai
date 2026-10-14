# fleetai

Parse a JarvisMD bug report into tickets, then send one ticket to a local
Cursor agent in `/Users/minh/repos/hba`.

```bash
conda activate dev
python main.py parse
python main.py
python main.py JMD-30SEP-05
python main.py verify
python main.py complete JMD-30SEP-05
```

See `docs/project.md`.
