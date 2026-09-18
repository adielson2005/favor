import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/wallet.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_skeleton.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/wallet_transaction_row.dart';

const _pageSize = 30;

/// Full paginated GET /wallet/transactions — wallet_screen.dart's "Últimas
/// movimentações" only ever shows 5. "Extrato" opens this with no filter;
/// "Ganhos" opens it with type=EARNING (the type credit_wallet uses for a
/// worker's cut of a completed order — see backend/routes/public.py).
class WalletStatementScreen extends ConsumerStatefulWidget {
  final String? type;
  final String title;
  const WalletStatementScreen({super.key, this.type, required this.title});

  @override
  ConsumerState<WalletStatementScreen> createState() => _WalletStatementScreenState();
}

class _WalletStatementScreenState extends ConsumerState<WalletStatementScreen> {
  final List<WalletTransaction> _items = [];
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  bool _error = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = false;
    });
    try {
      final page = await ref.read(walletRepositoryProvider).fetchTransactions(limit: _pageSize, offset: 0, type: widget.type);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page);
        _hasMore = page.length == _pageSize;
      });
    } catch (_) {
      if (mounted) setState(() => _error = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final page = await ref
          .read(walletRepositoryProvider)
          .fetchTransactions(limit: _pageSize, offset: _items.length, type: widget.type);
      if (!mounted) return;
      setState(() {
        _items.addAll(page);
        _hasMore = page.length == _pageSize;
      });
    } catch (_) {
      // Leave _hasMore as-is — the button just stays tappable to retry.
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              Expanded(child: Text(widget.title, style: theme.type.h2.copyWith(fontSize: 17))),
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
                            title: 'Não foi possível carregar o extrato.',
                            actionTitle: 'Tentar de novo',
                            onAction: _load,
                            theme: theme,
                          ),
                        ])
                      : _items.isEmpty
                          ? ListView(children: [
                              EmptyState(icon: Icons.receipt_long_outlined, title: 'Nenhuma movimentação ainda.', theme: theme),
                            ])
                          : ListView(
                              padding: const EdgeInsets.all(20),
                              children: [
                                ..._items.map((t) => WalletTransactionRow(transaction: t, theme: theme)),
                                if (_hasMore) ...[
                                  const SizedBox(height: 12),
                                  AppButton(
                                    title: 'Carregar mais',
                                    theme: theme,
                                    variant: AppButtonVariant.secondary,
                                    loading: _loadingMore,
                                    onPressed: _loadingMore ? null : _loadMore,
                                  ),
                                ],
                              ],
                            ),
            ),
          ),
        ]),
      ),
    );
  }
}
