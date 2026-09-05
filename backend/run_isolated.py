"""Launches the backend against the isolated test/migration environment
(backend/.env.isolated, database faze_isolated) on port 8001 — see
backend/backups/README.md. ENV_FILE has to be set before database.py (imported
transitively by server.py) reads it, so this can't just be a launch.json
runtimeArgs list; it needs to run before that import happens.
"""
import os

os.environ.setdefault("ENV_FILE", ".env.isolated")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8001)
