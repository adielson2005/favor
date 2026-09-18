import 'package:flutter/material.dart';

import '../models/wallet.dart';
import '../theme/app_theme.dart';

/// Shared by wallet_screen.dart's "últimas movimentações" preview and
/// wallet_statement_screen.dart's full paginated list — same row for both,
/// just different data sources.
class WalletTransactionRow extends StatelessWidget {
  final WalletTransaction transaction;
  final AppTheme theme;
  const WalletTransactionRow({super.key, required this.transaction, required this.theme});

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
