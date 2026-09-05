import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/notification_item.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/empty_state.dart';

/// Mirrors frontend/app/notifications.tsx exactly, including its honest
/// scope: this is an in-app feed, not real push notifications. Neither this
/// Flutter app nor the RN app has push infrastructure today (no
/// expo-notifications/FCM/APNs anywhere in the audited codebase) — the
/// backend only writes to a `notifications` collection this screen reads.
/// Real OS-level push is future work, not invented here.
const _typeIcons = {
  'proposal': Icons.mail_outline,
  'accept': Icons.check_circle_outline,
  'reject': Icons.cancel_outlined,
  'message': Icons.chat_bubble_outline,
  'status': Icons.flag_outlined,
  'review': Icons.star_outline,
};

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  List<NotificationItem> _items = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
    // Same as the RN screen: opening this list marks everything read, then
    // refreshes Home's bell-icon count.
    ref.read(notificationsRepositoryProvider).markAllRead().then((_) {
      ref.read(unreadControllerProvider.notifier).refresh();
    }).catchError((_) {});
  }

  Future<void> _load() async {
    try {
      final items = await ref.read(notificationsRepositoryProvider).fetchNotifications();
      if (mounted) setState(() => _items = items);
    } catch (_) {
      // Keep last known state.
    } finally {
      if (mounted) setState(() => _loading = false);
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
              const SizedBox(width: 6),
              Text('Notificações', style: theme.type.h1.copyWith(fontSize: 18)),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _items.isEmpty
                    ? Center(
                        child: EmptyState(
                          icon: Icons.notifications_off_outlined,
                          title: 'Nada por aqui.',
                          body: 'Avisaremos quando algo importante acontecer.',
                          theme: theme,
                        ),
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: _items.length,
                        separatorBuilder: (context, index) => Padding(
                          padding: const EdgeInsets.only(left: 74),
                          child: Divider(height: 1, color: colors.border),
                        ),
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          return InkWell(
                            onTap: item.orderId != null ? () => context.push('/order/${item.orderId}') : null,
                            child: Container(
                              color: item.read ? Colors.transparent : colors.surface,
                              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                              child: Row(children: [
                                Container(
                                  width: 40,
                                  height: 40,
                                  decoration: BoxDecoration(color: colors.primarySoft, shape: BoxShape.circle),
                                  child: Icon(_typeIcons[item.type] ?? Icons.notifications_outlined,
                                      size: 18, color: colors.primary),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Text(item.title, style: theme.type.bodyStrong),
                                    const SizedBox(height: 2),
                                    Text(item.body,
                                        style: theme.type.small.copyWith(color: colors.muted),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis),
                                  ]),
                                ),
                              ]),
                            ),
                          );
                        },
                      ),
          ),
        ]),
      ),
    );
  }
}
