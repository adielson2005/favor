import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import client, db
from routes.admin import router as admin_router
from routes.public import router as public_router
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
    yield
    client.close()


app = FastAPI(title="FAZÊ API", lifespan=lifespan)
app.include_router(public_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
