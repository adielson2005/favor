import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import client, db
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.public import router as public_router
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
    yield
    client.close()


app = FastAPI(title="fazum API", lifespan=lifespan)
app.include_router(auth_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
