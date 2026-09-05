"""Idempotent demo/reference data seeding for fazum."""
import os

from auth import hash_password
from database import db, new_id, now
from scripts.backfill_neighborhood_zones import ZONE_MAP

SEED_VERSION = 3
DEMO_PASSWORD = "faze2024"

ADMIN_ROLES = [
    {"key": "OWNER", "name": "Administrador principal"},
    {"key": "MANAGER", "name": "Gerente"},
    {"key": "SUPPORT", "name": "Suporte"},
    {"key": "MAINTENANCE", "name": "Manutenção"},
]

FEATURE_FLAGS = [
    {"key": "GOOGLE_LOGIN", "enabled": True, "description": "Login/cadastro com Google"},
    {"key": "WALLET", "enabled": True, "description": "Carteira digital"},
    {"key": "WITHDRAWAL", "enabled": True, "description": "Saques da carteira"},
    {"key": "URGENT_SERVICES", "enabled": True, "description": "Marcar pedidos como urgentes"},
    {"key": "RECURRING_SERVICES", "enabled": True, "description": "Pedidos recorrentes"},
]

NEIGHBORHOODS = {
    "bairro": [
        # Zona Central
        "Cidade Nova", "Primavera", "Maranhão", "Rio Verde", "Nova Vida", "União",
        "Liberdade I", "Liberdade II", "Da Paz", "Caetanópolis", "Guanabara",
        "Paraíso", "Esplanada", "Linha Verde",
        # Zona Norte
        "Beira Rio", "Parque dos Carajás", "Vila Rica", "Habitar Feliz", "Altamira",
        "Novo Horizonte", "Jardim Canadá", "Betânia", "Alto Bonito", "FAP",
        "Santa Luzia", "Novo Viver", "Vale do Sol", "Tropical", "Polo Moveleiro",
        # Zona Nordeste
        "Minérios", "Cidade Jardim",
        # Zona Sul
        "Parque das Nações", "São Lucas", "Brasília", "Morada Nova",
        "Jardim América", "Jardim Planalto",
        # Zona Sudeste
        "Nova Carajás", "Apoena", "Amazônia", "Alvorá", "Novo Brasil",
    ],
    "distrito": ["Núcleo Urbano de Carajás"],
}

CATEGORIES = [
    ("cat-entregas", "Entregas", "cube-outline", ["Buscar encomenda", "Entregar encomenda", "Documentos", "Pequenas compras", "Retirada em loja", "Entrega entre bairros", "Entrega urgente", "Entrega de chaves", "Transporte de objetos"]),
    ("cat-compras", "Compras", "cart-outline", ["Supermercado", "Farmácia", "Presentes", "Materiais", "Produtos específicos", "Retirada de pedido", "Compras rápidas"]),
    ("cat-casa", "Casa", "home-outline", ["Montagem de móveis", "Organização", "Limpeza", "Pequenas mudanças", "Carregar objetos", "Pequenos reparos", "Jardinagem", "Instalação simples"]),
    ("cat-tecnologia", "Tecnologia", "laptop-outline", ["Configurar computador", "Instalar programas", "Configurar celular", "Configurar impressora", "Configurar Wi-Fi", "Suporte técnico"]),
    ("cat-veiculos", "Veículos", "car-outline", ["Lavagem", "Levar para manutenção", "Buscar veículo", "Ajuda com bateria", "Pequenos serviços"]),
    ("cat-pets", "Pets", "paw-outline", ["Passeio", "Levar ao veterinário", "Buscar pet", "Cuidar do animal", "Alimentação"]),
    ("cat-documentos", "Documentos e Tarefas", "document-text-outline", ["Buscar documento", "Entregar documento", "Impressão", "Digitalização", "Tarefas administrativas"]),
    ("cat-eventos", "Eventos", "megaphone-outline", ["Montagem", "Desmontagem", "Carregar materiais", "Entrega de materiais", "Apoio em eventos"]),
    ("cat-profissionais", "Serviços Profissionais", "briefcase-outline", ["Fotografia", "Design", "Edição", "Informática", "Manutenção", "Assistência técnica"]),
    ("cat-outros", "Outros", "ellipsis-horizontal-outline", ["Outro tipo de ajuda"]),
]

USERS = [
    {"id": "demo-client", "name": "Marina Alves", "email": "marina@fazum.demo", "phone": "+5594991110001", "initials": "MA", "bio": "Moro em Parauapebas e uso o fazum para o dia a dia.", "rating": 4.9, "rating_count": 11, "jobs_done": 12, "neighborhood": "Cidade Nova", "verified_email": True, "verified_phone": True, "verified_identity": True, "is_admin": False},
    {"id": "demo-worker", "name": "João Ribeiro", "email": "joao@fazum.demo", "phone": "+5594991110002", "initials": "JR", "bio": "Faço entregas, montagens e pequenos serviços. Rápido e de confiança.", "rating": 4.9, "rating_count": 78, "jobs_done": 86, "neighborhood": "União", "verified_email": True, "verified_phone": True, "verified_identity": True, "is_admin": False},
    {"id": "worker-ana", "name": "Ana Souza", "email": "ana@fazum.demo", "phone": "+5594991110003", "initials": "AS", "bio": "Compras, pets e organização. Capricho em tudo.", "rating": 4.8, "rating_count": 39, "jobs_done": 42, "neighborhood": "Rio Verde", "verified_email": True, "verified_phone": True, "verified_identity": True, "is_admin": False},
    {"id": "worker-pedro", "name": "Pedro Lima", "email": "pedro@fazum.demo", "phone": "+5594991110004", "initials": "PL", "bio": "Técnico em informática. Configuro computadores e redes.", "rating": 4.7, "rating_count": 17, "jobs_done": 19, "neighborhood": "Beira Rio", "verified_email": True, "verified_phone": False, "verified_identity": False, "is_admin": False},
    {"id": "demo-admin", "name": "Equipe fazum", "email": "admin@fazum.demo", "phone": "+5594991110005", "initials": "FZ", "bio": "Administração da plataforma.", "rating": 5.0, "rating_count": 0, "jobs_done": 0, "neighborhood": "Cidade Nova", "verified_email": True, "verified_phone": True, "verified_identity": True, "is_admin": True},
]

ORDERS = [
    {"id": "order-1", "title": "Buscar encomenda nos Correios", "description": "Preciso que retirem uma caixa pequena nos Correios do centro e entreguem na minha casa ainda hoje.", "type": "favor", "category_id": "cat-entregas", "sub": "Buscar encomenda", "bairro": "Cidade Nova", "date_label": "Hoje", "time_label": "até 17:00", "budget": 25, "client_id": "demo-client", "fields": {"origem": "Correios — Centro", "destino": "Rua B, Cidade Nova"}},
    {"id": "order-2", "title": "Montar guarda-roupa de 6 portas", "description": "Guarda-roupa novo, ainda na caixa. As peças e o manual estão no local. Preciso de alguém com ferramentas.", "type": "servico", "category_id": "cat-casa", "sub": "Montagem de móveis", "bairro": "Rio Verde", "date_label": "Amanhã", "time_label": "manhã", "budget": 120, "client_id": "demo-client", "fields": {}},
    {"id": "order-3", "title": "Passear com cachorro dócil", "description": "Passeio de 30 minutos com um golden retriever muito tranquilo, perto da praça do bairro.", "type": "favor", "category_id": "cat-pets", "sub": "Passeio", "bairro": "Da Paz", "date_label": "Hoje", "time_label": "18:00", "budget": 30, "client_id": "demo-client", "fields": {"pet": "Golden retriever, dócil"}},
    {"id": "order-4", "title": "Compras de supermercado", "description": "Lista pequena com 12 itens. Pago o valor das compras na entrega, combinamos pelo chat.", "type": "favor", "category_id": "cat-compras", "sub": "Supermercado", "bairro": "Primavera", "date_label": "Hoje", "time_label": "qualquer horário", "budget": 35, "client_id": "demo-client", "fields": {"local_compra": "Supermercado do bairro"}},
    {"id": "order-5", "title": "Formatar e configurar notebook", "description": "Notebook lento, quero formatar, instalar os programas básicos e configurar o Wi-Fi.", "type": "servico", "category_id": "cat-tecnologia", "sub": "Configurar computador", "bairro": "Beira Rio", "date_label": "Esta semana", "time_label": "a combinar", "budget": 90, "client_id": "demo-client", "fields": {"equipamento": "Notebook Dell"}},
    {"id": "order-6", "title": "Lavar moto CG 160", "description": "Lavagem completa da moto, de preferência em casa. Tenho mangueira disponível.", "type": "favor", "category_id": "cat-veiculos", "sub": "Lavagem", "bairro": "Altamira", "date_label": "Amanhã", "time_label": "tarde", "budget": 40, "client_id": "demo-client", "fields": {"veiculo": "Honda CG 160"}},
    {"id": "order-7", "title": "Criar arte para Instagram", "description": "Preciso de 3 artes para divulgar uma lanchonete. Tenho as fotos e o logotipo prontos.", "type": "servico", "category_id": "cat-profissionais", "sub": "Design", "bairro": "União", "date_label": "Esta semana", "time_label": "", "budget": 150, "client_id": "demo-client", "fields": {"prazo": "Até sexta-feira"}},
    {"id": "order-8", "title": "Levar documentos ao cartório", "description": "Entregar um envelope lacrado no cartório do centro e trazer o comprovante de protocolo.", "type": "favor", "category_id": "cat-documentos", "sub": "Entregar documento", "bairro": "Cidade Nova", "date_label": "Hoje", "time_label": "antes das 16:00", "budget": 20, "client_id": "demo-client", "fields": {}},
]


async def ensure_seed():
    meta = await db.meta.find_one({"id": "seed"})
    version = (meta or {}).get("version", 0)

    if version < SEED_VERSION:
        # Reference data is rebuilt; user-generated content is preserved.
        await db.states.delete_many({})
        await db.cities.delete_many({})
        await db.neighborhoods.delete_many({})
        await db.categories.delete_many({})
        await db.subcategories.delete_many({})

        await db.states.insert_one({"id": "st-pa", "name": "Pará", "uf": "PA", "active": True})
        cities = [
            {"id": "city-parauapebas", "state_id": "st-pa", "name": "Parauapebas", "active": True},
            {"id": "city-canaa", "state_id": "st-pa", "name": "Canaã dos Carajás", "active": False},
            {"id": "city-curionopolis", "state_id": "st-pa", "name": "Curionópolis", "active": False},
            {"id": "city-eldorado", "state_id": "st-pa", "name": "Eldorado do Carajás", "active": False},
            {"id": "city-maraba", "state_id": "st-pa", "name": "Marabá", "active": False},
        ]
        await db.cities.insert_many(cities)

        hoods = []
        i = 0
        for kind, names in NEIGHBORHOODS.items():
            for name in names:
                i += 1
                hoods.append({"id": f"nb-{i}", "city_id": "city-parauapebas", "name": name, "kind": kind, "active": True, "zone": ZONE_MAP.get(name)})
        await db.neighborhoods.insert_many(hoods)

        for order_idx, (cid, name, icon, subs) in enumerate(CATEGORIES):
            await db.categories.insert_one({"id": cid, "name": name, "icon": icon, "order": order_idx, "active": True})
            for sub_idx, sub in enumerate(subs):
                await db.subcategories.insert_one({"id": f"{cid}-s{sub_idx}", "category_id": cid, "name": sub, "active": True})

        await db.meta.update_one({"id": "seed"}, {"$set": {"version": SEED_VERSION, "updated_at": now()}}, upsert=True)

    # Demo users/orders — only inserted when missing (never overwrite real content).
    hood_by_name = {h["name"]: h async for h in db.neighborhoods.find({"city_id": "city-parauapebas"})}
    for user in USERS:
        existing = await db.users.find_one({"id": user["id"]})
        if not existing:
            user = dict(user)
            hood = hood_by_name.get(user.pop("neighborhood"), {})
            active = user.get("verified_email") and user.get("verified_phone")
            user.update({
                "password_hash": hash_password(DEMO_PASSWORD), "preference": "both",
                "city_id": "city-parauapebas", "neighborhood_id": hood.get("id"), "blocked": False,
                "state_id": "st-pa", "account_status": "ACTIVE" if active else "PENDING_VERIFICATION",
                "email_verified_at": now() if user.get("verified_email") else None,
                "phone_verified_at": now() if user.get("verified_phone") else None,
                "member_since": "2025-08-01T00:00:00+00:00", "is_demo": True, "created_at": now(),
            })
            await db.users.insert_one(dict(user))
        else:
            updates = {}
            if not existing.get("password_hash"):
                updates["password_hash"] = hash_password(DEMO_PASSWORD)
            if not existing.get("preference"):
                updates["preference"] = "both"
            if not existing.get("phone") and user.get("phone"):
                updates["phone"] = user["phone"]
            if not existing.get("state_id"):
                updates["state_id"] = "st-pa"
            if not existing.get("account_status"):
                active = existing.get("verified_email") and existing.get("verified_phone")
                updates["account_status"] = "ACTIVE" if active else "PENDING_VERIFICATION"
            if existing.get("verified_email") and not existing.get("email_verified_at"):
                updates["email_verified_at"] = "2025-08-01T00:00:00+00:00"
            if existing.get("verified_phone") and not existing.get("phone_verified_at"):
                updates["phone_verified_at"] = "2025-08-01T00:00:00+00:00"
            # These accounts only ever carry demo data (never real user content), so
            # rename-in-place is safe: move a still-on-the-old-domain demo account to
            # its new address/name rather than leaving it permanently stale.
            if not existing.get("email") or existing.get("email", "").endswith("@faze.demo"):
                updates["email"] = user["email"]
            if existing.get("is_demo") and existing.get("name") == "Equipe FAZÊ":
                updates["name"] = user["name"]
            if existing.get("is_demo") and existing.get("bio") == "Moro em Parauapebas e uso o FAZÊ para o dia a dia.":
                updates["bio"] = user["bio"]
            if updates:
                await db.users.update_one({"id": user["id"]}, {"$set": updates})

    if await db.orders.count_documents({}) == 0:
        for order in ORDERS:
            sub = await db.subcategories.find_one({"category_id": order["category_id"], "name": order.pop("sub")})
            hood = hood_by_name.get(order.pop("bairro"), {})
            order.update({
                "subcategory_id": (sub or {}).get("id"), "city_id": "city-parauapebas",
                "neighborhood_id": hood.get("id"), "status": "published", "worker_id": None,
                "photos": [], "is_demo": True, "reviewed_by_client": False, "reviewed_by_worker": False,
                "created_at": now(),
            })
            await db.orders.insert_one(dict(order))

    # One demo proposal so the compare screen never starts empty.
    if await db.proposals.count_documents({}) == 0:
        await db.proposals.insert_one({"id": "prop-demo-1", "order_id": "order-2", "worker_id": "worker-ana", "amount": 110, "message": "Já montei mais de 20 guarda-roupas. Levo minhas ferramentas e deixo tudo limpo.", "eta": "Amanhã de manhã", "status": "pending", "is_demo": True, "created_at": now()})
        await db.proposals.insert_one({"id": "prop-demo-2", "order_id": "order-2", "worker_id": "worker-pedro", "amount": 130, "message": "Posso fazer amanhã cedo, tenho experiência com móveis planejados.", "eta": "Amanhã, 8h", "status": "pending", "is_demo": True, "created_at": now()})

    # Admin-panel RBAC roles — display records only; the actual permission sets
    # live in code (admin_permissions.py) so they can't silently drift from what
    # the backend actually enforces.
    # One-time rename: ATENDENTE -> SUPPORT (Fase 2 renamed the role to match the
    # spec's own wording). Safe as a plain field update since the role document is
    # just a display record and any admin_users row still pointing at the old key
    # gets renamed right after.
    await db.admin_roles.update_one({"key": "ATENDENTE"}, {"$set": {"key": "SUPPORT", "name": "Suporte"}})
    await db.admin_users.update_many({"role": "ATENDENTE"}, {"$set": {"role": "SUPPORT"}})
    for role in ADMIN_ROLES:
        await db.admin_roles.update_one({"key": role["key"]}, {"$setOnInsert": role}, upsert=True)

    # One seed OWNER account so the panel is usable out of the box. Dev-only
    # convenience — production must set its own ADMIN_SEED_EMAIL/PASSWORD (or just
    # create further accounts through the panel and deactivate this one).
    if await db.admin_users.count_documents({}) == 0:
        seed_email = os.environ.get("ADMIN_SEED_EMAIL", "admin@fazum.demo").lower()
        seed_password = os.environ.get("ADMIN_SEED_PASSWORD", DEMO_PASSWORD)
        await db.admin_users.insert_one({
            "id": new_id(), "name": "Equipe fazum", "email": seed_email,
            "password_hash": hash_password(seed_password), "role": "OWNER", "active": True,
            "token_version": 0, "totp_enabled": False, "last_login_at": None,
            "created_at": now(), "updated_at": now(),
        })

    # Feature flags — seeded reflecting the REAL current behavior of the app (all
    # on, since these are already-shipped capabilities), never overwriting a value
    # an admin has since changed via the panel.
    for flag in FEATURE_FLAGS:
        await db.feature_flags.update_one({"key": flag["key"]}, {"$setOnInsert": flag}, upsert=True)
