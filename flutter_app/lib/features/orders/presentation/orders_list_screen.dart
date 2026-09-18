import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/order.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_skeleton.dart';
import '../../../core/widgets/empty_state.dart';
import '../../auth/application/auth_controller.dart';
import '../../home/presentation/order_card.dart';

/// Full-list version of what home_screen.dart's "Ver todos" / "Ver pedidos
/// disponíveis" / category-tap used to dead-end into (home only ever shows
/// a capped preview of 20). Same fetchOrders query shape as home's own
/// _load — client mode = the caller's own orders, worker mode = nearby
/// published ones — with an optional category filter layered on top.
class OrdersListScreen extends ConsumerStatefulWidget {
  final String? categoryId;
  final String? categoryName;
  const OrdersListScreen({super.key, this.categoryId, this.categoryName});

  @override
  ConsumerState<OrdersListScreen> createState() => _OrdersListScreenState();
}

class _OrdersListScreenState extends ConsumerState<OrdersListScreen> {
  List<Order> _orders = [];
  bool _loading = true;
  bool _error = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final me = ref.read(authControllerProvider).user;
    final bootstrap = ref.read(bootstrapProvider).valueOrNull;
    if (me == null) return;
    final mode = ref.read(modeControllerProvider);
    final city = bootstrap?.cities.where((c) => c.id == me.cityId).firstOrNull ?? bootstrap?.cities.firstOrNull;

    setState(() {
      _loading = true;
      _error = false;
    });
    try {
      final repo = ref.read(ordersRepositoryProvider);
      final result = mode == 'client'
          ? await repo.fetchOrders(
              mine: true, status: 'published,accepted,in_progress,completion_requested,completed,cancelled',
              categoryId: widget.categoryId, limit: 100)
          : await repo.fetchOrders(cityId: city?.id, status: 'published', categoryId: widget.categoryId, limit: 100);
      final filtered = mode == 'worker' ? result.where((o) => o.clientId != me.id).toList() : result;
      if (!mounted) return;
      setState(() => _orders = filtered);
    } catch (_) {
      if (mounted) setState(() => _error = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final mode = ref.watch(modeControllerProvider);
    final isClient = mode == 'client';
    final title = widget.categoryName ??
        (isClient ? 'Seus pedidos' : 'Pedidos disponíveis');

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              Expanded(child: Text(title, style: theme.type.h2.copyWith(fontSize: 17))),
            ]),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: _loading
                  ? ListView(padding: const EdgeInsets.all(20), children: [
                      AppSkeleton(theme: theme),
                      const SizedBox(height: 10),
                      AppSkeleton(theme: theme),
                    ])
                  : _error
                      ? ListView(children: [
                          EmptyState(
                            icon: Icons.cloud_off_outlined,
                            title: 'Não foi possível carregar os pedidos.',
                            actionTitle: 'Tentar de novo',
                            onAction: _load,
                            theme: theme,
                          ),
                        ])
                      : _orders.isEmpty
                          ? ListView(children: [
                              EmptyState(
                                icon: Icons.eco_outlined,
                                title: isClient ? 'Você ainda não publicou nenhum pedido.' : 'Nenhum pedido encontrado.',
                                theme: theme,
                              ),
                            ])
                          : ListView.builder(
                              padding: const EdgeInsets.all(20),
                              itemCount: _orders.length,
                              itemBuilder: (context, i) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: OrderCard(
                                  order: _orders[i],
                                  theme: theme,
                                  showStatus: isClient,
                                  onTap: () => context.push('/order/${_orders[i].id}'),
                                ),
                              ),
                            ),
            ),
          ),
        ]),
      ),
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
