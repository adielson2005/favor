"""One-off migration: encrypt any admin_users.totp_secret/totp_secret_pending still
stored in plaintext (from before this field was covered by bank_encryption.py).
Idempotent — re-running it is a no-op for secrets already encrypted, since
encrypt_field() is only applied to values that don't already carry the "enc:v1:"
prefix. Mirrors scripts/encrypt_bank_data.py.

Usage (from backend/, with the target environment's .env already in place):
    ./venv/Scripts/python.exe -m scripts.encrypt_admin_totp
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bank_encryption import _PREFIX, encrypt_field  # noqa: E402
from database import db  # noqa: E402


async def main() -> None:
    scanned = 0
    migrated = 0
    async for admin in db.admin_users.find({}):
        scanned += 1
        updates = {}
        for field in ("totp_secret", "totp_secret_pending"):
            value = admin.get(field) or ""
            if value and not value.startswith(_PREFIX):
                updates[field] = encrypt_field(value)
        if updates:
            await db.admin_users.update_one({"_id": admin["_id"]}, {"$set": updates})
            migrated += 1
    print(f"Admin users scanned: {scanned}, migrated to encrypted-at-rest: {migrated}")


if __name__ == "__main__":
    asyncio.run(main())
