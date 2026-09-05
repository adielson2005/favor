import 'package:flutter/material.dart';

import '../../../core/models/order.dart';
import '../../../core/theme/app_theme.dart';

/// Mirrors frontend/src/components/OrderCard.tsx: category icon, title,
/// description, budget, urgent badge, neighborhood/city, date/time, and
/// either the order's own status (client's own orders) or its type label
/// (worker browsing).
class OrderCard extends StatelessWidget {
  final Order order;
  final bool showStatus;
  final VoidCallback onTap;
  final AppTheme theme;

  const OrderCard({
    super.key,
    required this.order,
    required this.theme,
    required this.onTap,
    this.showStatus = false,
  });

  Color _statusColor(AppTheme theme) {
    final colors = theme.colors;
    return switch (order.status) {
      'completed' => colors.green,
      'cancelled' => colors.danger,
      'published' => colors.muted,
      _ => colors.primary,
    };
  }

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final locationText = order.neighborhood ?? order.city ?? '';
    final timeText = order.timeLabel.isNotEmpty ? '${order.dateLabel} · ${order.timeLabel}' : order.dateLabel;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: colors.border),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(color: colors.primarySoft, borderRadius: BorderRadius.circular(13)),
              alignment: Alignment.center,
              child: Icon(Icons.auto_awesome, size: 19, color: colors.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(order.title, style: theme.type.bodyStrong, maxLines: 1, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 3),
                Text(order.description,
                    style: theme.type.small.copyWith(color: colors.muted), maxLines: 1, overflow: TextOverflow.ellipsis),
              ]),
            ),
            Text('R\$ ${order.budget.toStringAsFixed(0)}',
                style: theme.type.bodyStrong.copyWith(color: colors.green)),
          ]),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              if (order.urgent)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7),
                  height: 20,
                  decoration: BoxDecoration(color: colors.dangerSoft, borderRadius: BorderRadius.circular(8)),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.bolt, size: 11, color: colors.danger),
                    const SizedBox(width: 3),
                    Text('Urgente', style: TextStyle(color: colors.danger, fontWeight: FontWeight.bold, fontSize: 11)),
                  ]),
                ),
              if (locationText.isNotEmpty) _Meta(icon: Icons.location_on_outlined, text: locationText, theme: theme),
              if (timeText.isNotEmpty) _Meta(icon: Icons.access_time, text: timeText, theme: theme),
              Text(
                showStatus ? order.statusLabel : (order.type == 'favor' ? 'Favor' : 'Serviço'),
                style: TextStyle(
                  color: showStatus ? _statusColor(theme) : colors.faint,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ]),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  final IconData icon;
  final String text;
  final AppTheme theme;
  const _Meta({required this.icon, required this.text, required this.theme});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 13, color: colors.faint),
      const SizedBox(width: 4),
      Text(text, style: TextStyle(color: colors.muted, fontSize: 12)),
    ]);
  }
}
