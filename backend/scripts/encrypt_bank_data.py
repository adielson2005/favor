"""One-off migration: encrypt any bank_accounts.document/account_number still stored
in plaintext (from before bank_encryption.py existed). Idempotent — re-running it is
a no-op for documents already encrypted, since encrypt_field() is only applied to
values that don't already carry the "enc:v1:" prefix.

Usage (from backend/, with the target environment's .env already in place):
    ./venv/Scripts/python.exe -m scripts.encrypt_bank_data
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
    async for account in db.bank_accounts.find({}):
        scanned += 1
        updates = {}
        for field in ("document", "account_number"):
            value = account.get(field) or ""
            if value and not value.startswith(_PREFIX):
                updates[field] = encrypt_field(value)
        if updates:
            await db.bank_accounts.update_one({"_id": account["_id"]}, {"$set": updates})
            migrated += 1
    print(f"Bank accounts scanned: {scanned}, migrated to encrypted-at-rest: {migrated}")


if __name__ == "__main__":
    asyncio.run(main())
