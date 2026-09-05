"""One-off migration: set `zone` on every neighborhoods document, transcribed from
the zone groupings that already existed as source comments in `seed.py`'s
NEIGHBORHOODS dict (Zona Central/Norte/Nordeste/Sul/Sudeste) but were never
persisted. Idempotent — re-running only touches documents whose stored zone
differs from ZONE_MAP, a no-op on the second run. `distrito`'s single entry
("Núcleo Urbano de Carajás") has no zone grouping and is left unset.

Usage (from backend/, with the target environment's .env already in place):
    ./venv/Scripts/python.exe -m scripts.backfill_neighborhood_zones
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db  # noqa: E402

ZONE_MAP: dict[str, str] = {
    # Zona Central
    "Cidade Nova": "Zona Central", "Primavera": "Zona Central", "Maranhão": "Zona Central",
    "Rio Verde": "Zona Central", "Nova Vida": "Zona Central", "União": "Zona Central",
    "Liberdade I": "Zona Central", "Liberdade II": "Zona Central", "Da Paz": "Zona Central",
    "Caetanópolis": "Zona Central", "Guanabara": "Zona Central", "Paraíso": "Zona Central",
    "Esplanada": "Zona Central", "Linha Verde": "Zona Central",
    # Zona Norte
    "Beira Rio": "Zona Norte", "Parque dos Carajás": "Zona Norte", "Vila Rica": "Zona Norte",
    "Habitar Feliz": "Zona Norte", "Altamira": "Zona Norte", "Novo Horizonte": "Zona Norte",
    "Jardim Canadá": "Zona Norte", "Betânia": "Zona Norte", "Alto Bonito": "Zona Norte",
    "FAP": "Zona Norte", "Santa Luzia": "Zona Norte", "Novo Viver": "Zona Norte",
    "Vale do Sol": "Zona Norte", "Tropical": "Zona Norte", "Polo Moveleiro": "Zona Norte",
    # Zona Nordeste
    "Minérios": "Zona Nordeste", "Cidade Jardim": "Zona Nordeste",
    # Zona Sul
    "Parque das Nações": "Zona Sul", "São Lucas": "Zona Sul", "Brasília": "Zona Sul",
    "Morada Nova": "Zona Sul", "Jardim América": "Zona Sul", "Jardim Planalto": "Zona Sul",
    # Zona Sudeste
    "Nova Carajás": "Zona Sudeste", "Apoena": "Zona Sudeste", "Amazônia": "Zona Sudeste",
    "Alvorá": "Zona Sudeste", "Novo Brasil": "Zona Sudeste",
}


async def main() -> None:
    scanned = 0
    updated = 0
    async for n in db.neighborhoods.find({}):
        scanned += 1
        zone = ZONE_MAP.get(n["name"])
        if zone and n.get("zone") != zone:
            await db.neighborhoods.update_one({"_id": n["_id"]}, {"$set": {"zone": zone}})
            updated += 1
    print(f"Neighborhoods scanned: {scanned}, zone set/updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
