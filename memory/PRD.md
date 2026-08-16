# FAZÊ — PRD

## Problema
Moradores de Parauapebas precisam resolver pequenas tarefas, enquanto pessoas locais querem ganhar dinheiro realizando-as. O FAZÊ conecta os dois lados com um fluxo simples: criar pedido → propostas → aceite → chat → conclusão → avaliação mútua.

## Arquitetura
- Frontend: Expo SDK 54 / expo-router (file-based). Telas: onboarding, (tabs)/home|explore|messages|profile, create (wizard modal), order/[id], chat/[id], activity, notifications, admin.
- Fundação: `src/theme.tsx` (design system claro/escuro/sistema persistido), `src/state.tsx` (AppProvider: usuários demo, modo, catálogo, geo), `src/api.ts`, `src/components/ui.tsx` (Btn/Chip/Field/Sheet/Segmented/Stars/EmptyState...), `src/components/OrderCard.tsx`.
- Backend: FastAPI modular em `0.0.0.0:8001` rotas `/api` — `server.py`, `database.py`, `models.py`, `seed.py`, `routes/public.py`, `routes/admin.py`. MongoDB (Motor) com índices.

## Dados / Coleções
states, cities, neighborhoods (42 bairros oficiais de Parauapebas + distrito Núcleo Urbano de Carajás), categories (9) + subcategories, users, orders (type favor|servico, status published→accepted→in_progress→completed|cancelled), proposals, messages (text|image|system), reviews (mútuas, agregam rating), reports, blocks, favorites, notifications, admin_actions, meta (seed v2 idempotente).

## Perfis demo (sem auth — decisão do usuário)
- Modo "Preciso de ajuda" = demo-client (Marina Alves)
- Modo "Quero fazer" = demo-worker (João Ribeiro)
- Admin: demo-admin via query `admin_id` nas rotas /api/admin/* (rota /admin no app)

## Implementado — 13/06/2026 (Iteração 5, refinamento completo)
- Backend geográfico administrável (estados/cidades/bairros com ativar/desativar/adicionar).
- Categorias/subcategorias no banco, administráveis.
- Wizard de criação em 6 etapas com campos adaptados por categoria; correção definitiva do rodapé cortado (P0 anterior).
- Explorar com busca tokenizada (ex: "guarda roupa"), filtros (categoria, tipo, valor, bairro).
- Propostas reais (valor/prazo/mensagem), comparação e aceite; mensagens do sistema; chat com texto/imagem (base64) e polling.
- Conclusão com timeline (Aceito → Em andamento → Concluído) e avaliação mútua 1–5 estrelas.
- Denúncias, favoritos, notificações internas, bloqueio (backend), níveis de reputação.
- Painel admin (/admin): visão geral, usuários (bloquear/verificar), pedidos, categorias, localidades, denúncias.
- Onboarding 3 telas; tema Claro/Escuro/Sistema; empty/loading/error states humanos.
- Testes: 26/26 backend (pytest) + E2E frontend aprovado (iteration_5.json). 2 bugs achados e corrigidos (race no admin, bloco duplicado no detalhe).

## Backlog priorizado
- P1: Cadastro/Login real (JWT) — usuário optou por adiar para a próxima atualização.
- P2: PWA (manifest/service worker), anexo de fotos no pedido (wizard), seletor de cidade no Explorar quando houver 2+ cidades ativas.
- P2: bloqueio de usuário exposto na UI (backend pronto), verificação automática de identidade.
- Fora do MVP: pagamentos online, GPS em tempo real, áudio/vídeo.
