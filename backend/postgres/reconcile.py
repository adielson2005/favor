"""Read-only reconciliation gate for a staged FAZUM MongoDB migration.

This command never changes the application routing or either source database. Its
report is evidence for a human cutover decision, not a cutover mechanism.
"""
from __future__ import annotations
import argparse, asyncio, json, os
from decimal import Decimal, ROUND_HALF_UP
import asyncpg

FINANCIAL_FLOATS={"deposits":"amount","withdrawals":"amount"}
WALLET_COLUMNS=("available_cents","pending_cents","processing_cents","total_received_cents","total_spent_cents")
REQUIRED_CANONICAL={
 "states":"states","cities":"cities","neighborhoods":"neighborhoods","categories":"categories",
 "subcategories":"subcategories","users":"users","orders":"orders","wallets":"wallets",
 "wallet_transactions":"wallet_transactions","bank_accounts":"bank_accounts","deposits":"deposits",
 "withdrawals":"withdrawals","payments":"payments","payment_events":"payment_events",
}
def env(k):
    v=os.environ.get(k)
    if not v: raise RuntimeError(f"{k} is required")
    return v
def cents(v): return int((Decimal(str(v or 0))*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
async def q(pg,sql,*args): return await pg.fetchval(sql,*args)

async def source_counts(pg,run):
    rows=await pg.fetch("SELECT collection_name,count(*) AS n FROM migration_staging WHERE migration_run_id=$1 GROUP BY collection_name",run)
    return {r["collection_name"]:r["n"] for r in rows}
async def source_money(pg,run,collection):
    rows=await pg.fetch("SELECT payload FROM migration_staging WHERE migration_run_id=$1 AND collection_name=$2",run,collection)
    if collection=="wallets":
        return {field:sum((r["payload"].get(field,0) or 0) for r in rows) for field in WALLET_COLUMNS}
    field=FINANCIAL_FLOATS.get(collection)
    return {"amount_cents":sum(cents(r["payload"].get(field,0)) for r in rows)} if field else {}
async def target_money(pg,table):
    if table=="wallets":
        row=await pg.fetchrow("SELECT "+",".join(f"COALESCE(sum({x}),0) AS {x}" for x in WALLET_COLUMNS)+" FROM wallets")
        return dict(row)
    return {"amount_cents":await q(pg,f"SELECT COALESCE(sum(amount_cents),0) FROM {table}")}

async def main(a):
    pg=await asyncpg.connect(env("POSTGRES_DSN"))
    try:
        run=await pg.fetchrow("SELECT id,status,details FROM migration_runs WHERE id=$1::uuid",a.run_id)
        if not run: raise RuntimeError("migration run not found")
        report={"run_id":a.run_id,"run_status":run["status"],"checks":{},"blocking":False}
        expected=(run["details"] or {}).get("source_counts",{})
        staged=await source_counts(pg,run["id"])
        report["checks"]["staging_counts"]={"expected":expected,"actual":staged,"ok":expected==staged}
        if expected!=staged: report["blocking"]=True

        canonical={}
        for collection,table in REQUIRED_CANONICAL.items():
            source=staged.get(collection,0)
            mapped=await q(pg,"SELECT count(*) FROM legacy_id_map WHERE migration_run_id=$1 AND collection_name=$2 AND postgres_table=$3",run["id"],collection,table)
            canonical[collection]={"source":source,"mapped":mapped,"ok":source==mapped}
            if source!=mapped: report["blocking"]=True
        report["checks"]["canonical_identity_map"]=canonical

        money={}
        for collection,table in (("wallets","wallets"),("deposits","deposits"),("withdrawals","withdrawals")):
            source=await source_money(pg,run["id"],collection); target=await target_money(pg,table)
            money[collection]={"source":source,"target":target,"ok":source==target}
            if source!=target: report["blocking"]=True
        payment_source=await pg.fetch("SELECT payload FROM migration_staging WHERE migration_run_id=$1 AND collection_name='payments'",run["id"])
        payment_expected={"gross_amount_cents":sum(cents(r["payload"].get("gross_amount")) for r in payment_source),
                          "commission_amount_cents":sum(cents(r["payload"].get("commission_amount")) for r in payment_source),
                          "worker_net_amount_cents":sum(cents(r["payload"].get("worker_net_amount")) for r in payment_source)}
        target_row=await pg.fetchrow("SELECT "+",".join(f"COALESCE(sum({x}),0) AS {x}" for x in payment_expected)+" FROM payments")
        money["payments"]={"source":payment_expected,"target":dict(target_row),"ok":payment_expected==dict(target_row)}
        if not money["payments"]["ok"]: report["blocking"]=True
        report["checks"]["money_totals"]=money

        idempotency=await pg.fetch("""SELECT collection_name,payload->>'idempotency_key' AS key,count(*) AS n
            FROM migration_staging WHERE migration_run_id=$1 AND payload ? 'idempotency_key'
            AND COALESCE(payload->>'idempotency_key','')<>'' GROUP BY collection_name,payload->>'idempotency_key' HAVING count(*)>1""",run["id"])
        report["checks"]["source_idempotency_duplicates"]=[dict(x) for x in idempotency]
        if idempotency: report["blocking"]=True
        integrity=await pg.fetchrow("""SELECT
          (SELECT count(*) FROM payments WHERE gross_amount_cents<>commission_amount_cents+worker_net_amount_cents) AS invalid_payment_math,
          (SELECT count(*) FROM wallets WHERE available_cents<0 OR pending_cents<0 OR processing_cents<0) AS negative_wallets,
          (SELECT count(*) FROM migration_issues WHERE migration_run_id=$1 AND severity='BLOCKING' AND resolved_at IS NULL) AS open_blocking_issues""",run["id"])
        report["checks"]["database_invariants"]=dict(integrity)
        if any(integrity.values()): report["blocking"]=True
        report["cutover_allowed"]=False
        report["next_action"]="Human approval and an API feature-flag rollout are required even when all checks pass."
        await pg.execute("UPDATE migration_runs SET details=details || $2::jsonb WHERE id=$1",run["id"],json.dumps({"reconciliation":report}))
        print(json.dumps(report,ensure_ascii=False,default=str,indent=2))
        if report["blocking"]: raise SystemExit(2)
    finally: await pg.close()
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--run-id",required=True);asyncio.run(main(p.parse_args()))
