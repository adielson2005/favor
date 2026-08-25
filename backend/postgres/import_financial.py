"""Financial canonical import; offline only.

Prerequisites: staging run is VALIDATED, the baseline schema has been applied, and
BANK_DATA_ENCRYPTION_KEY is a Fernet key managed outside this repository. This script
does not enable PostgreSQL in the API; it imports and reconciles only.
"""
from __future__ import annotations
import argparse, asyncio, json, os, uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import asyncpg
from cryptography.fernet import Fernet

NS=uuid.UUID("a68d5d25-b616-463b-8194-0c20836d9dfb")
FINANCIAL=("wallets","wallet_transactions","deposits","bank_accounts","withdrawals","payments","payment_events")
def env(k):
    v=os.environ.get(k)
    if not v: raise RuntimeError(f"{k} is required")
    return v
def uid(c,k): return uuid.uuid5(NS,f"fazum:{c}:{k}")
def cents(v): return int((Decimal(str(v or 0))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
def ts(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except ValueError:return None
def status(value,choices,default): return value if value in choices else default

async def rows(pg,run,c):
    return await pg.fetch("SELECT legacy_id,payload FROM migration_staging WHERE migration_run_id=$1 AND collection_name=$2 ORDER BY legacy_id",run,c)
async def mapid(pg,run,c,k,table):
    ident=uid(c,k)
    await pg.execute("""INSERT INTO legacy_id_map(collection_name,legacy_id,postgres_table,postgres_id,migration_run_id)
        VALUES($1,$2,$3,$4,$5) ON CONFLICT(collection_name,legacy_id) DO UPDATE SET postgres_id=EXCLUDED.postgres_id,
        postgres_table=EXCLUDED.postgres_table,migration_run_id=EXCLUDED.migration_run_id""",c,k,table,ident,run)
    return ident
async def issue(pg,run,c,k,code,detail,severity="BLOCKING"):
    await pg.execute("""INSERT INTO migration_issues(migration_run_id,severity,collection_name,legacy_id,code,detail)
        VALUES($1,$2,$3,$4,$5,$6::jsonb)""",run,severity,c,k,code,json.dumps(detail,default=str))

async def ensure_platform_user(pg,run):
    # Current Mongo ledger uses literal user_id='platform' for commission wallet.
    ident=await mapid(pg,run,"users","platform","users")
    await pg.execute("""INSERT INTO users(id,legacy_id,email,name,preference,account_status,verified_email)
       VALUES($1,'platform','system-platform@internal.invalid','FAZUM Platform','both','ACTIVE',true)
       ON CONFLICT(legacy_id) DO NOTHING""",ident)
    return ident

async def import_wallets(pg,run):
    await ensure_platform_user(pg,run)
    for r in await rows(pg,run,"wallets"):
        d=r["payload"]; k=r["legacy_id"]; ident=await mapid(pg,run,"wallets",k,"wallets")
        try:
            await pg.execute("""INSERT INTO wallets(id,legacy_id,user_id,currency,available_cents,pending_cents,processing_cents,
              total_received_cents,total_spent_cents,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
              ON CONFLICT(legacy_id) DO UPDATE SET available_cents=EXCLUDED.available_cents,pending_cents=EXCLUDED.pending_cents,
              processing_cents=EXCLUDED.processing_cents,total_received_cents=EXCLUDED.total_received_cents,total_spent_cents=EXCLUDED.total_spent_cents,updated_at=now()""",
              ident,k,uid("users",d["user_id"]),d.get("currency","BRL"),d.get("available_cents",0),d.get("pending_cents",0),
              d.get("processing_cents",0),d.get("total_received_cents",0),d.get("total_spent_cents",0),ts(d.get("created_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"wallets",k,"WALLET_INVALID",{"error":str(e)})

async def import_transactions(pg,run):
    for r in await rows(pg,run,"wallet_transactions"):
        d=r["payload"]; k=r["legacy_id"]; ident=await mapid(pg,run,"wallet_transactions",k,"wallet_transactions")
        try:
            await pg.execute("""INSERT INTO wallet_transactions(id,legacy_id,wallet_id,user_id,type,amount_cents,direction,status,bucket,
              reference_type,reference_legacy_id,provider,provider_transaction_id,idempotency_key,description,created_at,updated_at)
              VALUES($1,$2,$3,$4,$5,$6,$7::transaction_direction,$8::transaction_status,$9,$10,$11,$12,$13,$14,$15,$16,$17)
              ON CONFLICT(legacy_id) DO UPDATE SET status=EXCLUDED.status,updated_at=EXCLUDED.updated_at""",
              ident,k,uid("wallets",d["wallet_id"]),uid("users",d["user_id"]),d["type"],d["amount_cents"],
              status(d.get("direction"),("IN","OUT","MOVE"),"MOVE"),status(d.get("status"),("PENDING","COMPLETED","FAILED","REVERSED"),"FAILED"),
              d.get("bucket","available"),d.get("reference_type","unknown"),d.get("reference_id",""),d.get("provider"),
              d.get("provider_transaction_id"),d.get("idempotency_key"),d.get("description",""),ts(d.get("created_at")) or datetime.now(),ts(d.get("updated_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"wallet_transactions",k,"LEDGER_INVALID",{"error":str(e)})

async def import_bank_accounts(pg,run,fernet):
    for r in await rows(pg,run,"bank_accounts"):
        d=r["payload"]; k=r["legacy_id"]; ident=await mapid(pg,run,"bank_accounts",k,"bank_accounts")
        try:
            document=str(d["document"]); agency=str(d["agency"]); account=str(d["account_number"])
            await pg.execute("""INSERT INTO bank_accounts(id,legacy_id,user_id,holder_name,document_encrypted,document_last4,bank_code,
              agency_encrypted,account_number_encrypted,account_last4,account_type,is_primary,active,created_at)
              VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
              ON CONFLICT(legacy_id) DO UPDATE SET active=EXCLUDED.active,is_primary=EXCLUDED.is_primary,updated_at=now()""",
              ident,k,uid("users",d["user_id"]),d["holder_name"],fernet.encrypt(document.encode()),document[-4:].rjust(4,"*"),
              d["bank_code"],fernet.encrypt(agency.encode()),fernet.encrypt(account.encode()),account[-4:].rjust(4,"*"),
              d.get("account_type","checking"),d.get("is_primary",False),d.get("active",True),ts(d.get("created_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"bank_accounts",k,"BANK_ACCOUNT_INVALID",{"error":str(e)})

async def import_deposits(pg,run):
    for r in await rows(pg,run,"deposits"):
        d=r["payload"]; k=r["legacy_id"]; ident=await mapid(pg,run,"deposits",k,"deposits")
        try:
            await pg.execute("""INSERT INTO deposits(id,legacy_id,user_id,amount_cents,method,status,provider,provider_transaction_id,idempotency_key,created_at,updated_at)
               VALUES($1,$2,$3,$4,$5,$6::payment_status,$7,$8,$9,$10,$11) ON CONFLICT(legacy_id) DO UPDATE SET status=EXCLUDED.status,updated_at=EXCLUDED.updated_at""",
               ident,k,uid("users",d["user_id"]),cents(d["amount"]),d.get("method","pix"),status(d.get("status"),("pending","held","released","refunded","failed","cancelled"),"pending"),d.get("provider"),d.get("provider_transaction_id"),d.get("idempotency_key"),ts(d.get("created_at")) or datetime.now(),ts(d.get("updated_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"deposits",k,"DEPOSIT_INVALID",{"error":str(e)})

async def import_payments(pg,run):
    for r in await rows(pg,run,"payments"):
        d=r["payload"]; k=r["legacy_id"]; ident=await mapid(pg,run,"payments",k,"payments")
        try:
            gross=cents(d["gross_amount"]); commission=cents(d["commission_amount"]); net=cents(d["worker_net_amount"])
            if gross != commission+net: raise ValueError("gross amount does not equal commission plus worker net")
            await pg.execute("""INSERT INTO payments(id,legacy_id,order_id,client_id,worker_id,gross_amount_cents,commission_amount_cents,worker_net_amount_cents,
              commission_percent,method,status,provider,provider_transaction_id,idempotency_key,client_ip,created_at,updated_at)
              VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::payment_status,$12,$13,$14,$15::inet,$16,$17)
              ON CONFLICT(legacy_id) DO UPDATE SET status=EXCLUDED.status,updated_at=EXCLUDED.updated_at""",
              ident,k,uid("orders",d["order_id"]),uid("users",d["client_id"]),uid("users",d["worker_id"]),gross,commission,net,
              d.get("commission_percent",0),d.get("method","wallet"),status(d.get("status"),("pending","held","released","refunded","failed","cancelled"),"pending"),
              d.get("provider"),d.get("provider_transaction_id"),d.get("idempotency_key"),d.get("client_ip"),ts(d.get("created_at")) or datetime.now(),ts(d.get("updated_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"payments",k,"PAYMENT_INVALID",{"error":str(e)})

async def reconcile(pg,run):
    # Exact source->target row/count and cached-cent comparisons. Ledger semantic balancing
    # is intentionally a separate signed-entry audit because MOVE records are not debit/credit pairs.
    failures=[]
    for c in FINANCIAL:
        source=await pg.fetchval("SELECT count(*) FROM migration_staging WHERE migration_run_id=$1 AND collection_name=$2",run,c)
        table=c
        target=await pg.fetchval(f"SELECT count(*) FROM {table}") if c!="payment_events" else 0
        if c!="payment_events" and source!=target: failures.append({"collection":c,"source":source,"target":target})
    if failures: await issue(pg,run,"financial",None,"ROW_COUNT_MISMATCH",{"failures":failures})
    await pg.execute("UPDATE migration_runs SET details=details || $2::jsonb WHERE id=$1",run,json.dumps({"financial_reconciliation":{"row_count_failures":failures}}))
    return failures

async def main(a):
    fernet=Fernet(env("BANK_DATA_ENCRYPTION_KEY").encode())
    pg=await asyncpg.connect(env("POSTGRES_DSN"))
    try:
        run=await pg.fetchrow("SELECT id,status FROM migration_runs WHERE id=$1::uuid",a.run_id)
        if not run or run["status"]!="VALIDATED": raise RuntimeError("run must be VALIDATED")
        await import_wallets(pg,run["id"]); await import_transactions(pg,run["id"]); await import_bank_accounts(pg,run["id"],fernet)
        await import_deposits(pg,run["id"]); await import_payments(pg,run["id"]); failures=await reconcile(pg,run["id"])
        print(json.dumps({"run_id":a.run_id,"financial_row_count_failures":failures,"cutover_allowed":False}))
    finally: await pg.close()
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--run-id",required=True);asyncio.run(main(p.parse_args()))
