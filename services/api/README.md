# services/api

FastAPI/Python service for bodesign web APIs, EDA jobs, MCP tool handlers, validation, and export orchestration.

Run locally from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r services/api/requirements.txt
./webctl.sh start
```

Then open `http://127.0.0.1:8765/bodesign/`.

Initial endpoints:

- `GET /health`
- `GET /`
- `GET /bodesign`
- `GET /bodesign/`
- `GET /bodesign/routes`
- `GET /bodesign/api/routes`
- `GET /api/projects`
