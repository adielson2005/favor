# PostgreSQL migration foundation

This directory is additive. MongoDB remains the production source of truth until a signed cutover succeeds.

## Audit: collections actually used

Runtime collections (31): `users`, `auth_accounts`, `verification_tokens`, `security_events`, `states`, `cities`, `neighborhoods`, `categories`, `subcategories`, `orders`, `proposals`, `messages`, `reviews`, `reports`, `blocks`, `favorites`, `notifications`, `wallets`, `wallet_transactions`, `deposits`, `bank_accounts`, `withdrawals`, `payments`, `payment_events`, `disputes`, `risk_flags`, `platform_config`, `admin_users`, `admin_roles`, `admin_actions`, `feature_flags`, and `tickets`. `meta` is used only by the seed process.

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

No production migration should run automatically in CI or on application startup.

## pgAdmin / DBeaver access

Do not expose PostgreSQL publicly. Production PostgreSQL must listen on a private network only. Use an SSH tunnel or a zero-trust/VPN bastion with named individual database users, TLS verification, IP allow-listing, least privilege, and MFA on the bastion. The application has a separate non-superuser role; its database credentials cannot create users, extensions, or databases. DBeaver/pgAdmin users should be read-only by default. Administrative write access is temporary and audited.

For local development only, `docker-compose.postgres.local.yml` binds Postgres to `127.0.0.1`; it is deliberately unsuitable for production.
