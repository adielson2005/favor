# Isolated test/migration environment

This directory holds a `mongodump` snapshot of `faze_dev`, restored into a
**separate database** (`faze_isolated`) on the same local MongoDB server —
same tool that produced `faze_dev/`, just pointed at a different `DB_NAME`,
so the two never collide.

## What's here

- `faze_dev/` — the raw mongodump output (one `.bson` + `.metadata.json` pair
  per collection). This is the actual backup archive; keep it if you want to
  re-restore later or take it off this machine for safekeeping.
- MongoDB Database Tools (`mongodump.exe`/`mongorestore.exe`) live outside the
  repo at `Nova pasta/tools/mongodb-database-tools-windows-x86_64-100.11.0/bin`
  — not checked in; a ~66MB download from `fastdl.mongodb.org`.

## Re-running the restore

```bash
MONGOTOOLS="/c/Users/USER/Desktop/Nova pasta/tools/mongodb-database-tools-windows-x86_64-100.11.0/bin"
"$MONGOTOOLS/mongorestore.exe" --uri="mongodb://localhost:27017" \
  --nsFrom="faze_dev.*" --nsTo="faze_isolated.*" \
  --drop \
  "/c/Users/USER/Desktop/Nova pasta/favor/backend/backups"
```

`--drop` wipes `faze_isolated` first, so this is safe to re-run any time you
want a fresh copy of whatever `faze_dev` looked like when the dump was taken.
To capture a *new* snapshot of the current dev data instead of reusing this
one:

```bash
"$MONGOTOOLS/mongodump.exe" --uri="mongodb://localhost:27017" --db=faze_dev \
  --out="/c/Users/USER/Desktop/Nova pasta/favor/backend/backups"
```

## Running the backend against the isolated database

`backend/.env.isolated` has its own `MONGO_URL`/`DB_NAME=faze_isolated` and
carries the **same** `BANK_DATA_ENCRYPTION_KEY` as `backend/.env` (required —
the restored `bank_accounts.document`/`account_number` fields were encrypted
with that key before the backup was taken; a different key can't decrypt
them). `database.py` picks the file via the `ENV_FILE` env var:

```bash
cd backend
export ENV_FILE=.env.isolated
./venv/Scripts/python.exe -m uvicorn server:app --host 0.0.0.0 --port 8001
```

Or via `.claude/launch.json`'s `favor-backend-isolated` config (port 8001,
alongside `favor-backend` on 8000 for the normal dev database). Omitting
`ENV_FILE` always falls back to the default `.env`/`faze_dev` — nothing about
normal dev/prod startup changes.

## Bank data encryption

`document` (CPF/CNPJ) and `account_number` on `bank_accounts` are encrypted
at rest with Fernet (`backend/bank_encryption.py`), keyed by
`BANK_DATA_ENCRYPTION_KEY`. Existing plaintext records (from before this was
added) were migrated in place with:

```bash
./venv/Scripts/python.exe -m scripts.encrypt_bank_data
```

Safe to re-run — it only touches values that don't already carry the
`enc:v1:` prefix, so it's a no-op on records already encrypted. Run it again
against any environment (`ENV_FILE=...`) that still has plaintext bank data.
