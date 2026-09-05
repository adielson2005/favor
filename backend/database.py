import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
# ENV_FILE lets an isolated/migration environment (e.g. backend/.env.isolated) be
# selected without overwriting the default .env — set it in the shell before starting
# uvicorn/pytest/a script. Defaults to the normal dev file so nothing else changes.
load_dotenv(ROOT_DIR / os.environ.get("ENV_FILE", ".env"))

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())
