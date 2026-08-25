"""Canonical importer for the non-sensitive FAZUM domain.

Run only after stage_mongo.py reports VALIDATED. It is idempotent, keeps the original
identifier in legacy_id, and records every incompatible record as a BLOCKING issue.
It deliberately does not import bank accounts, wallet balances, ledger, deposits,
withdrawals or payment balances: those require an approved financial reconciliation.
"""
from __future__ import annotations
import argparse, asyncio, json, os, uuid
from datetime import datetime
import asyncpg

NS = uuid.UUID("a68d5d25-b616-463b-8194-0c20836d9dfb")
SAFE_COLLECTIONS = ("states","cities","neighborhoods","categories","subcategories","users",
                    "auth_accounts","orders","proposals","messages","reviews","favorites",
                    "reports","disputes","notifications","admin_roles","admin_users",
                    "feature_flags","tickets","security_events","risk_flags")
SENSITIVE_COLLECTIONS = ("wallets","wallet_transactions","deposits","bank_accounts","withdrawals","payments","payment_events")

def env(name):
    value=os.environ.get(name)
    if not value: raise RuntimeError(f"{name} is required")
    return value

def uid(collection, legacy):
    return uuid.uuid5(NS, f"fazum:{collection}:{legacy}")

def ts(value):
    if not value: return None
    if isinstance(value, datetime): return value
    try: return datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except ValueError: return None

def cents(value):
    # Source uses floats. Converting through str avoids binary float rounding.
    from decimal import Decimal, ROUND_HALF_UP
    return int((Decimal(str(value or 0))*100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

async def issue(pg, run, collection, legacy, code, detail, severity="BLOCKING"):
    await pg.execute("""INSERT INTO migration_issues(migration_run_id,severity,collection_name,legacy_id,code,detail)
                      VALUES($1,$2,$3,$4,$5,$6::jsonb)""",
                     run,severity,collection,legacy,code,json.dumps(detail,default=str))

async def source_rows(pg, run, collection):
    return await pg.fetch("""SELECT legacy_id,payload FROM migration_staging
                             WHERE migration_run_id=$1 AND collection_name=$2 ORDER BY legacy_id""",run,collection)

async def map_id(pg, run, collection, legacy, table):
    result=uid(collection,legacy)
    await pg.execute("""INSERT INTO legacy_id_map(collection_name,legacy_id,postgres_table,postgres_id,migration_run_id)
                      VALUES($1,$2,$3,$4,$5)
                      ON CONFLICT(collection_name,legacy_id) DO UPDATE
                      SET postgres_table=EXCLUDED.postgres_table, postgres_id=EXCLUDED.postgres_id,
                          migration_run_id=EXCLUDED.migration_run_id""",collection,legacy,table,result,run)
    return result

async def import_geography(pg, run):
    for coll, table, sql in (
      ("states","states","INSERT INTO states(id,legacy_id,name,uf,active) VALUES($1,$2,$3,$4,$5) ON CONFLICT(legacy_id) DO UPDATE SET name=EXCLUDED.name,uf=EXCLUDED.uf,active=EXCLUDED.active"),
      ("cities","cities","INSERT INTO cities(id,legacy_id,state_id,name,active) VALUES($1,$2,$3,$4,$5) ON CONFLICT(legacy_id) DO UPDATE SET state_id=EXCLUDED.state_id,name=EXCLUDED.name,active=EXCLUDED.active"),
      ("neighborhoods","neighborhoods","INSERT INTO neighborhoods(id,legacy_id,city_id,name,kind,active) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(legacy_id) DO UPDATE SET city_id=EXCLUDED.city_id,name=EXCLUDED.name,kind=EXCLUDED.kind,active=EXCLUDED.active"),
    ):
        for row in await source_rows(pg,run,coll):
            d=row["payload"]; key=row["legacy_id"]; ident=await map_id(pg,run,coll,key,table)
            try:
                if coll=="states": args=(ident,key,d["name"],d["uf"],d.get("active",True))
                elif coll=="cities": args=(ident,key,uid("states",d["state_id"]),d["name"],d.get("active",True))
                else: args=(ident,key,uid("cities",d["city_id"]),d["name"],d.get("kind","bairro"),d.get("active",True))
                await pg.execute(sql,*args)
            except Exception as e: await issue(pg,run,coll,key,"RELATIONSHIP_INVALID",{"error":str(e)})

async def import_taxonomy(pg, run):
    for coll, table, sql in (
      ("categories","categories","INSERT INTO categories(id,legacy_id,name,icon,display_order,active) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(legacy_id) DO UPDATE SET name=EXCLUDED.name,icon=EXCLUDED.icon,display_order=EXCLUDED.display_order,active=EXCLUDED.active"),
      ("subcategories","subcategories","INSERT INTO subcategories(id,legacy_id,category_id,name,active) VALUES($1,$2,$3,$4,$5) ON CONFLICT(legacy_id) DO UPDATE SET category_id=EXCLUDED.category_id,name=EXCLUDED.name,active=EXCLUDED.active"),
    ):
        for row in await source_rows(pg,run,coll):
            d=row["payload"]; key=row["legacy_id"]; ident=await map_id(pg,run,coll,key,table)
            try:
                args=(ident,key,d["name"],d.get("icon","sparkles-outline"),d.get("order",0),d.get("active",True)) if coll=="categories" else (ident,key,uid("categories",d["category_id"]),d["name"],d.get("active",True))
                await pg.execute(sql,*args)
            except Exception as e: await issue(pg,run,coll,key,"RELATIONSHIP_INVALID",{"error":str(e)})

async def import_users(pg, run):
    sql="""INSERT INTO users(id,legacy_id,email,phone,password_hash,name,initials,bio,avatar_url,city_id,neighborhood_id,
           preference,rating,rating_count,jobs_done,verified_email,verified_phone,verified_identity,email_verified_at,
           phone_verified_at,account_status,blocked,token_version,notification_prefs,member_since,created_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::preference_type,$13,$14,$15,$16,$17,$18,$19,$20,$21::account_status,$22,$23,$24::jsonb,$25,$26)
           ON CONFLICT(legacy_id) DO UPDATE SET email=EXCLUDED.email,phone=EXCLUDED.phone,name=EXCLUDED.name,bio=EXCLUDED.bio,
           city_id=EXCLUDED.city_id,neighborhood_id=EXCLUDED.neighborhood_id,account_status=EXCLUDED.account_status,blocked=EXCLUDED.blocked,updated_at=now()"""
    for row in await source_rows(pg,run,"users"):
        d=row["payload"]; key=row["legacy_id"]; ident=await map_id(pg,run,"users",key,"users")
        try:
            status=d.get("account_status","ACTIVE")
            if status not in ("PENDING_VERIFICATION","ACTIVE","SUSPENDED","BLOCKED","DELETED"): status="ACTIVE"
            pref=d.get("preference","both")
            if pref not in ("client","worker","both"): pref="both"
            await pg.execute(sql,ident,key,d.get("email"),d.get("phone"),d.get("password_hash"),d.get("name",""),
              d.get("initials"),d.get("bio",""),None,uid("cities",d["city_id"]) if d.get("city_id") else None,
              uid("neighborhoods",d["neighborhood_id"]) if d.get("neighborhood_id") else None,pref,d.get("rating",5),
              d.get("rating_count",0),d.get("jobs_done",0),d.get("verified_email",False),d.get("verified_phone",False),
              d.get("verified_identity",False),ts(d.get("email_verified_at")),ts(d.get("phone_verified_at")),status,
              d.get("blocked",False),d.get("token_version",0),json.dumps(d.get("notification_prefs",{})),ts(d.get("member_since")) or ts(d.get("created_at")),ts(d.get("created_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"users",key,"USER_INVALID",{"error":str(e)})

async def import_orders(pg, run):
    sql="""INSERT INTO orders(id,legacy_id,client_id,worker_id,category_id,subcategory_id,city_id,neighborhood_id,title,description,type,status,
           date_label,time_label,budget_cents,fields,urgent,recurrence,reviewed_by_client,reviewed_by_worker,pre_dispute_status,
           external_payment_restricted,started_at,completed_at,cancelled_at,created_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::order_status,$13,$14,$15,$16::jsonb,$17,$18,$19,$20,$21::order_status,$22,$23,$24,$25,$26)
           ON CONFLICT(legacy_id) DO UPDATE SET worker_id=EXCLUDED.worker_id,status=EXCLUDED.status,updated_at=now()"""
    for row in await source_rows(pg,run,"orders"):
        d=row["payload"]; key=row["legacy_id"]; ident=await map_id(pg,run,"orders",key,"orders")
        if d.get("photos"): await issue(pg,run,"orders",key,"BASE64_MEDIA_PENDING",{"count":len(d["photos"])})
        try:
            status=d.get("status","published")
            if status not in ("published","accepted","in_progress","completion_requested","completed","cancelled","disputed"): status="published"
            pre=d.get("pre_dispute_status"); pre=pre if pre in ("published","accepted","in_progress","completion_requested","completed","cancelled","disputed") else None
            await pg.execute(sql,ident,key,uid("users",d["client_id"]),uid("users",d["worker_id"]) if d.get("worker_id") else None,
              uid("categories",d["category_id"]),uid("subcategories",d["subcategory_id"]) if d.get("subcategory_id") else None,
              uid("cities",d["city_id"]),uid("neighborhoods",d["neighborhood_id"]) if d.get("neighborhood_id") else None,
              d["title"],d.get("description",""),d.get("type","favor"),status,d.get("date_label","Hoje"),d.get("time_label",""),
              cents(d.get("budget")),json.dumps(d.get("fields",{})),d.get("urgent",False),d.get("recurrence","none"),
              d.get("reviewed_by_client",False),d.get("reviewed_by_worker",False),pre,d.get("external_payment_restricted",False),
              ts(d.get("started_at")),ts(d.get("completed_at")),ts(d.get("cancelled_at")),ts(d.get("created_at")) or datetime.now())
        except Exception as e: await issue(pg,run,"orders",key,"ORDER_INVALID",{"error":str(e)})

async def main(args):
    pg=await asyncpg.connect(env("POSTGRES_DSN"))
    try:
        run=await pg.fetchrow("SELECT id,status FROM migration_runs WHERE id=$1::uuid",args.run_id)
        if not run or run["status"]!="VALIDATED": raise RuntimeError("run must exist and be VALIDATED")
        # Do not wrap the full import in one transaction: invalid legacy records are
        # quarantined individually and must not poison an otherwise valid batch.
        await import_geography(pg,run["id"]); await import_taxonomy(pg,run["id"]); await import_users(pg,run["id"]); await import_orders(pg,run["id"])
        for collection in SENSITIVE_COLLECTIONS:
            count=await pg.fetchval("SELECT count(*) FROM migration_staging WHERE migration_run_id=$1 AND collection_name=$2",run["id"],collection)
            if count: await issue(pg,run["id"],collection,None,"SENSITIVE_DOMAIN_PENDING",{"documents":count},"WARNING")
        blocking=await pg.fetchval("SELECT count(*) FROM migration_issues WHERE migration_run_id=$1 AND severity='BLOCKING' AND resolved_at IS NULL",run["id"])
        print(json.dumps({"run_id":args.run_id,"blocking_issues":blocking,"cutover_allowed":False}))
    finally: await pg.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--run-id",required=True); asyncio.run(main(parser.parse_args()))
