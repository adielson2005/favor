import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/models/wallet.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_skeleton.dart';

/// Mirrors frontend/app/wallet/index.tsx: gradient "card" balance display
/// (same brand navy→green gradient), show/hide toggle persisted the same
/// way, and a recent-transactions list from the real ledger. Deposit via
/// PIX/ASAAS is intentionally not wired here — it needs a publicly
/// reachable webhook URL this environment doesn't have yet (the same
/// production-readiness gap already flagged earlier this session), so the
/// button is present but honestly says so rather than pretending to work.
class WalletScreen extends ConsumerStatefulWidget {
  const WalletScreen({super.key});

  @override
  ConsumerState<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends ConsumerState<WalletScreen> {
  static const _hideBalanceKey = 'faze:wallet-hide-balance';

  WalletBalance? _wallet;
  List<WalletTransaction> _recent = [];
  bool _loading = true;
  bool _hidden = false;

  @override
  void initState() {
    super.initState();
    _hydrateHidden();
    _load();
  }

  Future<void> _hydrateHidden() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) setState(() => _hidden = prefs.getBool(_hideBalanceKey) ?? false);
  }

  Future<void> _toggleHidden() async {
    setState(() => _hidden = !_hidden);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_hideBalanceKey, _hidden);
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(walletRepositoryProvider);
      final results = await Future.wait([repo.fetchWallet(), repo.fetchTransactions(limit: 5)]);
      if (!mounted) return;
      setState(() {
        _wallet = results[0] as WalletBalance;
        _recent = results[1] as List<WalletTransaction>;
      });
    } catch (_) {
      // Keep last known state — same as the RN screen's bare try/catch.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _money(double v) => _hidden ? 'R\$ ••••' : 'R\$ ${v.toStringAsFixed(2).replaceAll('.', ',')}';

  void _notAvailableYet(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$feature ainda não foi construído nesta fase.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final wallet = _wallet;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              Expanded(child: Text('Carteira', style: theme.type.h2.copyWith(fontSize: 17))),
            ]),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_loading || wallet == null)
                    Column(children: [
                      AppSkeleton(theme: theme, height: 180, radius: 20),
                      const SizedBox(height: 12),
                      AppSkeleton(theme: theme, height: 80),
                    ])
                  else ...[
                    _buildBalanceCard(theme, wallet),
                    const SizedBox(height: 16),
                    _buildShortcuts(theme),
                    const SizedBox(height: 24),
                    Text('Últimas movimentações', style: theme.type.h2.copyWith(fontSize: 16)),
                    const SizedBox(height: 10),
                    if (_recent.isEmpty)
                      Text('Nenhuma movimentação ainda.', style: theme.type.body.copyWith(color: colors.muted))
                    else
                      ..._recent.map((t) => _TransactionRow(transaction: t, theme: theme)),
                  ],
                ],
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _buildBalanceCard(AppTheme theme, WalletBalance wallet) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF091323), Color(0xFF0A7335)],
        ),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('fazumPay', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
          IconButton(
            onPressed: _toggleHidden,
            icon: Icon(_hidden ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                color: Colors.white70, size: 19),
          ),
        ]),
        const SizedBox(height: 12),
        const Text('Saldo disponível', style: TextStyle(color: Colors.white70, fontSize: 11)),
        Text(_money(wallet.available),
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 38, letterSpacing: -1)),
        const SizedBox(height: 12),
        Row(children: [
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Pendente', style: TextStyle(color: Colors.white60, fontSize: 11)),
            Text(_money(wallet.pending), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
          ]),
          const SizedBox(width: 24),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Processando', style: TextStyle(color: Colors.white60, fontSize: 11)),
            Text(_money(wallet.processing), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
          ]),
        ]),
      ]),
    );
  }

  Widget _buildShortcuts(AppTheme theme) {
    final colors = theme.colors;
    final shortcuts = [
      (Icons.qr_code, 'Depositar', () => _notAvailableYet('Depósito via Pix')),
      (Icons.arrow_upward, 'Sacar', () => context.push('/wallet/withdraw')),
      (Icons.trending_up, 'Ganhos', () => _notAvailableYet('Extrato de ganhos')),
      (Icons.receipt_long_outlined, 'Extrato', () => _notAvailableYet('Extrato completo')),
      (Icons.account_balance_outlined, 'Contas', () => context.push('/wallet/bank-accounts')),
    ];
    return Row(
      children: shortcuts
          .map((s) => Expanded(
                child: InkWell(
                  onTap: s.$3,
                  borderRadius: BorderRadius.circular(16),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(color: colors.alt, shape: BoxShape.circle),
                        child: Icon(s.$1, size: 19, color: colors.ink),
                      ),
                      const SizedBox(height: 6),
                      Text(s.$2, style: TextStyle(fontSize: 11, color: colors.muted), textAlign: TextAlign.center),
                    ]),
                  ),
                ),
              ))
          .toList(),
    );
  }
}

class _TransactionRow extends StatelessWidget {
  final WalletTransaction transaction;
  final AppTheme theme;
  const _TransactionRow({required this.transaction, required this.theme});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final isIn = transaction.direction == 'IN';
    final sign = isIn ? '+' : (transaction.direction == 'OUT' ? '-' : '');
    final color = isIn ? colors.green : (transaction.direction == 'OUT' ? colors.danger : colors.muted);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(color: colors.alt, shape: BoxShape.circle),
          child: Icon(
            isIn ? Icons.arrow_downward : Icons.arrow_upward,
            size: 16,
            color: colors.muted,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(transaction.description, style: theme.type.small.copyWith(fontWeight: FontWeight.bold)),
            Text(transaction.status, style: theme.type.micro.copyWith(color: colors.faint)),
          ]),
        ),
        Text('$sign R\$ ${transaction.amount.toStringAsFixed(2)}',
            style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
      ]),
    );
  }
}
