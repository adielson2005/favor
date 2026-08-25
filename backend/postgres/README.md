# PostgreSQL migration foundation

This directory is additive. MongoDB remains the production source of truth until a signed cutover succeeds.

## Audit: collections actually used

Runtime collections (32): `users`, `auth_accounts`, `verification_tokens`, `security_events`, `states`, `cities`, `neighborhoods`, `categories`, `subcategories`, `orders`, `proposals`, `messages`, `reviews`, `reports`, `blocks`, `favorites`, `notifications`, `wallets`, `wallet_transactions`, `deposits`, `bank_accounts`, `withdrawals`, `payments`, `payment_events`, `disputes`, `risk_flags`, `platform_config`, `admin_users`, `admin_roles`, `admin_actions`, `feature_flags`, and `tickets`. `meta` is used only by the seed process.

The Mongo indexes declared by `server.py` are mirrored by keys/unique indexes in the baseline; the migration must add indexes that match the live query plans before cutover. Notable query paths are marketplace browse `orders(city_id,status,created_at)`, message timeline, notification inbox, wallet history, ticket queue, risk queue, user email/phone lookup, one proposal per worker/order, and idempotency keys.

## Compatibility decisions

- Existing string UUIDs are retained as `legacy_id`; foreign keys use PostgreSQL UUIDs through `legacy_id_map`.
- Existing float values are converted once to integer centavos using Decimal string conversion. The app must stop accepting floats before PostgreSQL becomes writable.
- Mongo embedded arrays become child tables: order photos, dispute evidence, ticket messages, notification deliveries, permission assignments, and status history.
- Image base64 must be copied to private object storage and replaced by storage keys before final cutover. It must not be moved into PostgreSQL.
- `reports.target_id` remains polymorphic during migration as `target_legacy_id`; resolve it to typed FKs only after all target records validate.
- The current `admin_actions` collection is mutable in Mongo. PostgreSQL makes it append-only; maintenance must use a privileged archival procedure, never UPDATE/DELETE.
- `users.is_admin` must not authorize anything after cutover. `admin_users -> admin_roles -> role_permissions` is the authority.
- Order status changes currently update the order document without history. New code must insert `order_status_history` in the same PostgreSQL transaction.

## Safe runbook

1. Put the app in maintenance/read-only mode and record the Mongo oplog/high-water timestamp.
2. Create an encrypted immutable Mongo backup with `mongodump --archive --gzip`; store checksum, key reference, and retention metadata outside the application host.
3. Restore the backup into an isolated Mongo instance; never migrate from the live primary.
4. Create a fresh PostgreSQL database and apply `migrations/0001_fazum_baseline.sql`.
5. Run an importer in batches. Every inserted record must first upsert `legacy_id_map`; use `migration_runs(source,source_fingerprint)` to reject a mismatched rerun.
6. Validate per collection: source count, destination count, missing IDs, FK orphan count, monetary totals in centavos, and duplicate idempotency/provider event keys.
7. Perform a delta import from the recorded high-water mark, validate again, then switch the backend using a feature flag. Keep Mongo read-only for the rollback window.
8. Rollback means: switch the feature flag to Mongo, preserve PostgreSQL for forensics, and replay no financial webhook twice. Do **not** restore over either live database.

## Implemented offline staging command

After applying `0001_fazum_baseline.sql` and `0002_migration_staging.sql` to an empty PostgreSQL database, install `requirements-migration.txt` in an isolated migration environment. Set `MONGO_URL`, `DB_NAME`, and `POSTGRES_DSN` only in that environment, then run:

`python stage_mongo.py --backup-dir <encrypted-backup-volume>`

The command invokes `mongodump` through a temporary config file, hashes the resulting archive incrementally, stages every document as lossless JSONB, and validates all 32 collection counts. It records an immutable run row and refuses to change completed or rolled-back runs. A `VALIDATED` staging run is **not** a permission to route application traffic to PostgreSQL; canonical table mapping, FK/orphan checks, balance reconciliation, delta capture and feature-flag cutover still remain mandatory.

No production migration should run automatically in CI or on application startup.

## Implemented read-only reconciliation gate

`python reconcile.py --run-id <validated-run-uuid>` validates source/staging counts, canonical ID-map coverage, money totals in centavos, duplicate idempotency keys, payment arithmetic, negative cached balances, and open blocking migration issues. It saves the report against the migration run and exits non-zero on a blocking mismatch. It cannot enable cutover or alter MongoDB.

## Implemented financial import (offline, reconciled)

`import_financial.py --run-id <validated-run-uuid>` imports wallets, ledger records, deposits, bank accounts, withdrawals, payments and provider events. It requires `BANK_DATA_ENCRYPTION_KEY` (a Fernet key supplied only at execution time) and encrypts document, agency and account-number fields before they reach PostgreSQL. Values formerly stored as floats are converted through Decimal to integer centavos.

The financial importer checks staging-to-target row counts and registers failures in `migration_issues`. It preserves the special Mongo `platform` wallet through a dedicated internal platform user. It does not by itself prove ledger semantic balance, resolve every canonical non-financial table, or authorize cutover.

## Implemented canonical import (partial by design)

`import_canonical.py --run-id <validated-run-uuid>` imports the non-sensitive relational foundation: geography, categories, subcategories, users and orders. It is idempotent through `legacy_id_map` and writes malformed relations and base64 media as `migration_issues` instead of skipping them.

The importer explicitly does **not** import wallet/ledger, deposits, bank accounts, withdrawals, payments or payment events into canonical financial tables. These records must be migrated only with a financially reconciled, transactionally balanced importer and envelope encryption for bank-account fields. This safety boundary means that `cutover_allowed` remains false after the current importer.

## pgAdmin / DBeaver access

Do not expose PostgreSQL publicly. Production PostgreSQL must listen on a private network only. Use an SSH tunnel or a zero-trust/VPN bastion with named individual database users, TLS verification, IP allow-listing, least privilege, and MFA on the bastion. The application has a separate non-superuser role; its database credentials cannot create users, extensions, or databases. DBeaver/pgAdmin users should be read-only by default. Administrative write access is temporary and audited.

For local development only, `docker-compose.postgres.local.yml` binds Postgres to `127.0.0.1`; it is deliberately unsuitable for production.
