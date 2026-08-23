import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import client, db
from routes.admin import router as admin_router
from routes.admin_auth import router as admin_auth_router
from routes.auth import router as auth_router
from routes.public import router as public_router
from routes.tickets import router as tickets_router
from routes.wallet import router as wallet_router
from seed import ensure_seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_seed()
    await db.orders.create_index([("city_id", 1), ("status", 1), ("created_at", -1)])
    await db.orders.create_index("client_id")
    await db.proposals.create_index("order_id")
    await db.messages.create_index([("order_id", 1), ("created_at", 1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.reviews.create_index("to_id")
    await db.users.create_index("email", unique=True, sparse=True)
    await db.users.create_index("phone", unique=True, sparse=True)
    await db.verification_tokens.create_index([("user_id", 1), ("type", 1), ("created_at", -1)])
    await db.verification_tokens.create_index("expires_at")
    await db.wallets.create_index("user_id", unique=True)
    await db.wallet_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.wallet_transactions.create_index("idempotency_key", unique=True, sparse=True)
    await db.deposits.create_index("user_id")
    await db.deposits.create_index("idempotency_key", unique=True, sparse=True)
    await db.withdrawals.create_index("user_id")
    await db.withdrawals.create_index("idempotency_key", unique=True, sparse=True)
    await db.bank_accounts.create_index("user_id")
    await db.payments.create_index("order_id", unique=True)
    await db.disputes.create_index("order_id")
    await db.payment_events.create_index("event_id", unique=True)
    await db.orders.create_index("worker_id")
    await db.proposals.create_index("worker_id")
    await db.favorites.create_index([("user_id", 1), ("order_id", 1)])
    await db.reports.create_index([("target_type", 1), ("target_id", 1)])
    await db.blocks.create_index("user_id")
    await db.risk_flags.create_index([("status", 1), ("created_at", -1)])
    await db.security_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.auth_accounts.create_index([("provider", 1), ("provider_account_id", 1)], unique=True)
    await db.auth_accounts.create_index("user_id")
    await db.admin_users.create_index("email", unique=True)
    await db.admin_roles.create_index("key", unique=True)
    await db.feature_flags.create_index("key", unique=True)
    await db.tickets.create_index([("created_by", 1), ("created_at", -1)])
    await db.tickets.create_index([("status", 1), ("category", 1)])
    yield
    client.close()


app = FastAPI(title="fazum API", lifespan=lifespan)
app.include_router(auth_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(admin_auth_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# The app authenticates with a Bearer token (Authorization header), never cookies, so
# CORS "credentials" mode is never actually used — allow_credentials=True combined with
# a wildcard origin is both unnecessary and a spec-invalid combination browsers reject.
app.add_middleware(CORSMiddleware, allow_credentials=False, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
