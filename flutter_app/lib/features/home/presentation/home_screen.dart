import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/order.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_skeleton.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/segmented_control.dart';
import '../../auth/application/auth_controller.dart';
import 'order_card.dart';

/// Mirrors frontend/app/(tabs)/home.tsx: greeting + city, notification bell,
/// email-verification nudge, the "Preciso de ajuda"/"Quero fazer" mode
/// toggle, mode-dependent hero CTA, horizontally-scrolling categories from
/// the real /bootstrap, and a live orders list (own orders as client,
/// nearby published orders as worker) from the real /orders.
/// "Ver todos" / "Ver pedidos disponíveis" / category taps all open
/// OrdersListScreen (the same fetchOrders shape as this screen's own _load,
/// just uncapped and optionally category-filtered).
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  List<Order> _orders = [];
  bool _loading = true;
  bool _error = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _load();
      ref.read(unreadControllerProvider.notifier).refresh();
    });
  }

  Future<void> _load() async {
    final me = ref.read(authControllerProvider).user;
    final bootstrap = ref.read(bootstrapProvider).valueOrNull;
    if (me == null) return;

    final mode = ref.read(modeControllerProvider);
    final city = bootstrap?.cities.where((c) => c.id == me.cityId).firstOrNull ??
        bootstrap?.cities.firstOrNull;

    setState(() => _error = false);
    try {
      final repo = ref.read(ordersRepositoryProvider);
      final result = mode == 'client'
          ? await repo.fetchOrders(mine: true, status: 'published,accepted,in_progress', limit: 20)
          : await repo.fetchOrders(cityId: city?.id, status: 'published', limit: 20);
      final filtered = mode == 'worker' ? result.where((o) => o.clientId != me.id).toList() : result;
      if (!mounted) return;
      setState(() => _orders = filtered);
    } catch (_) {
      if (mounted) setState(() => _error = true);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final auth = ref.watch(authControllerProvider);
    final bootstrapAsync = ref.watch(bootstrapProvider);
    final mode = ref.watch(modeControllerProvider);
    final unread = ref.watch(unreadControllerProvider);
    final me = auth.user;

    if (me == null) return Scaffold(backgroundColor: colors.bg);

    if (_error) {
      return Scaffold(
        backgroundColor: colors.bg,
        body: Center(
          child: EmptyState(
            icon: Icons.cloud_off_outlined,
            title: 'Não conseguimos carregar isso agora.',
            body: 'Verifique sua conexão e tente novamente.',
            actionTitle: 'Tentar novamente',
            onAction: () {
              setState(() => _loading = true);
              _load();
            },
            theme: theme,
          ),
        ),
      );
    }

    final isClient = mode == 'client';
    final bootstrap = bootstrapAsync.valueOrNull;
    final city = bootstrap?.cities.where((c) => c.id == me.cityId).firstOrNull ?? bootstrap?.cities.firstOrNull;
    final nearby = _orders.take(3).toList();
    final firstName = me.name.split(' ').first;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.only(bottom: 32),
            children: [
              const SizedBox(height: 8),
              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(children: [
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Olá, $firstName', style: theme.type.h1.copyWith(fontSize: 22)),
                      const SizedBox(height: 2),
                      Row(children: [
                        Icon(Icons.location_on_outlined, size: 13, color: colors.muted),
                        const SizedBox(width: 4),
                        Text('${city?.name ?? "Parauapebas"}, PA',
                            style: theme.type.small.copyWith(color: colors.muted)),
                      ]),
                    ]),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: colors.surface,
                      shape: BoxShape.circle,
                      border: Border.all(color: colors.border),
                    ),
                    child: IconButton(
                      onPressed: () => context.push('/wallet'),
                      icon: Icon(Icons.account_balance_wallet_outlined, size: 19, color: colors.ink),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Stack(children: [
                    Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: colors.surface,
                        shape: BoxShape.circle,
                        border: Border.all(color: colors.border),
                      ),
                      child: IconButton(
                        onPressed: () => context.push('/notifications'),
                        icon: Icon(Icons.notifications_outlined, size: 19, color: colors.ink),
                      ),
                    ),
                    if (unread > 0)
                      Positioned(
                        top: 8,
                        right: 9,
                        child: Container(
                          width: 9,
                          height: 9,
                          decoration: BoxDecoration(
                            color: colors.danger,
                            shape: BoxShape.circle,
                            border: Border.all(color: colors.surface, width: 1.5),
                          ),
                        ),
                      ),
                  ]),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: () => context.push('/profile'),
                    child: AppAvatar(initials: me.initials, theme: theme),
                  ),
                ]),
              ),

              // Email verification nudge
              if (!me.verifiedEmail)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                  child: InkWell(
                    onTap: () => context.push('/auth/verify-email'),
                    borderRadius: BorderRadius.circular(14),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(color: colors.accentSoft, borderRadius: BorderRadius.circular(14)),
                      child: Row(children: [
                        Icon(Icons.mark_email_unread_outlined, size: 18, color: colors.accent),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text('Confirme seu e-mail para proteger sua conta.',
                              style: theme.type.small.copyWith(fontWeight: FontWeight.bold)),
                        ),
                        Icon(Icons.chevron_right, size: 16, color: colors.faint),
                      ]),
                    ),
                  ),
                ),

              // Mode switch
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
                child: SegmentedControl(
                  theme: theme,
                  value: mode,
                  options: const [
                    SegmentedOption('client', 'Preciso de ajuda'),
                    SegmentedOption('worker', 'Quero fazer'),
                  ],
                  onChanged: (m) {
                    ref.read(modeControllerProvider.notifier).setMode(m);
                    setState(() => _loading = true);
                    _load();
                  },
                ),
              ),

              // Hero
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 26, 20, 0),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(
                    isClient ? 'Precisa de uma mão?' : 'Encontre algo para fazer.',
                    style: theme.type.display.copyWith(fontSize: 26),
                  ),
                  const SizedBox(height: 16),
                  if (isClient) ...[
                    InkWell(
                      onTap: () => context.push('/create'),
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        height: 54,
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        decoration: BoxDecoration(
                          color: colors.surface,
                          border: Border.all(color: colors.border),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Row(children: [
                          Icon(Icons.search, size: 18, color: colors.faint),
                          const SizedBox(width: 10),
                          Text('O que você precisa?', style: TextStyle(color: colors.faint, fontSize: 15)),
                        ]),
                      ),
                    ),
                    const SizedBox(height: 12),
                    AppButton(title: 'Pedir ajuda', theme: theme, onPressed: () => context.push('/create')),
                  ] else
                    AppButton(title: 'Ver pedidos disponíveis', theme: theme, onPressed: () => context.push('/orders')),
                ]),
              ),

              // Categories
              Padding(
                padding: const EdgeInsets.only(top: 30),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Text('Categorias', style: theme.type.h2.copyWith(fontSize: 17)),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 86,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      children: bootstrapAsync.isLoading
                          ? List.generate(
                              4,
                              (i) => Padding(
                                padding: const EdgeInsets.only(right: 10),
                                child: SizedBox(width: 88, child: AppSkeleton(theme: theme, height: 86, radius: 16)),
                              ),
                            )
                          : (bootstrap?.categories ?? []).map((cat) {
                              return Padding(
                                padding: const EdgeInsets.only(right: 10),
                                child: InkWell(
                                  onTap: () => context.push(
                                      '/orders?category_id=${Uri.encodeComponent(cat.id)}&category_name=${Uri.encodeComponent(cat.name)}'),
                                  borderRadius: BorderRadius.circular(16),
                                  child: Container(
                                    width: 88,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                    decoration: BoxDecoration(
                                      color: colors.surface,
                                      border: Border.all(color: colors.border),
                                      borderRadius: BorderRadius.circular(16),
                                    ),
                                    child: Column(children: [
                                      Icon(Icons.auto_awesome, size: 21, color: colors.primary),
                                      const SizedBox(height: 8),
                                      Text(
                                        cat.name.split(' ').first,
                                        style: TextStyle(color: colors.ink, fontSize: 11, fontWeight: FontWeight.w600),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        textAlign: TextAlign.center,
                                      ),
                                    ]),
                                  ),
                                ),
                              );
                            }).toList(),
                    ),
                  ),
                ]),
              ),

              // Orders
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 30, 20, 0),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Text(isClient ? 'Seus pedidos' : 'Pedidos perto de você',
                        style: theme.type.h2.copyWith(fontSize: 17)),
                    TextButton(
                      onPressed: () => context.push('/orders'),
                      child: Text('Ver todos', style: TextStyle(color: colors.primary, fontWeight: FontWeight.bold, fontSize: 13)),
                    ),
                  ]),
                  if (_loading)
                    Column(children: [
                      AppSkeleton(theme: theme),
                      const SizedBox(height: 10),
                      AppSkeleton(theme: theme),
                    ])
                  else if (nearby.isEmpty)
                    isClient
                        ? EmptyState(
                            icon: Icons.description_outlined,
                            title: 'Você ainda não publicou nenhum pedido.',
                            actionTitle: 'Publicar pedido',
                            onAction: () => context.push('/create'),
                            theme: theme,
                          )
                        : EmptyState(
                            icon: Icons.eco_outlined,
                            title: 'Nenhum pedido por perto agora.',
                            body: 'Volte mais tarde ou explore outras categorias.',
                            theme: theme,
                          )
                  else
                    Column(
                      children: nearby
                          .map((order) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: OrderCard(
                                  order: order,
                                  theme: theme,
                                  showStatus: isClient,
                                  onTap: () => context.push('/order/${order.id}'),
                                ),
                              ))
                          .toList(),
                    ),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
