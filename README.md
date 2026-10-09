# fazum

Marketplace hiperlocal de serviços para Parauapebas-PA. Conecta quem precisa
resolver uma tarefa com quem quer fazer — publicar pedido → propostas →
aceite → chat → conclusão → avaliação mútua.

## Estrutura do repositório

- **`backend/`** — API FastAPI (`/api`), MongoDB como fonte de verdade,
  autenticação JWT real, carteira/pagamentos (ASAAS PIX), verificação de
  e-mail/telefone, painel admin. Uma migração de catálogo geográfico
  (estado/cidade/bairro) para PostgreSQL existe em paralelo
  (`alembic/`, `geo_catalog_repo.py`) mas ainda não é a fonte de dados ativa
  da API — veja o comentário em `backend/.env`.
- **`flutter_app/`** — app mobile (Android/iOS) em Flutter/Dart, cliente
  oficial do backend acima. Riverpod + go_router + dio. Veja
  `flutter_app/README.md` para rodar.

## Rodando o backend

```
cd backend
python -m venv venv && venv/Scripts/activate   # ou source venv/bin/activate
pip install -r requirements.txt
# configure backend/.env (veja os comentários no próprio arquivo)
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## Rodando o app Flutter

```
cd flutter_app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000   # emulador Android
```

Testes (`flutter test`) rodam contra o backend real, não mockado — suba o
backend antes de rodar a suíte.

## Deploy em produção (Render)

O backend é deployado no [Render](https://render.com/) a partir do `Dockerfile`
na raiz do repositório (contexto = raiz, mas o build só copia `backend/` pra
dentro da imagem — veja o próprio `Dockerfile`). `render.yaml` descreve o
serviço como Blueprint: crie o Web Service escolhendo "Docker" como ambiente,
ou use "New + → Blueprint" apontando pra este repositório.

Variáveis de ambiente de produção (segredos reais, nunca commitados) ficam em
`backend/.env.production.local` — copie cada uma para o painel do Render.
`SEED_DEMO_DATA=false` já vem fixo no `render.yaml` (evita recriar as contas
demo com senha pública no banco de produção). Banco de dados é MongoDB Atlas
(configurado via `MONGO_URL` no mesmo arquivo), independente de qual serviço
hospeda o backend.
