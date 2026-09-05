import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models/bootstrap.dart';
import 'networking/api_client.dart';
import 'repositories/blocks_repository.dart';
import 'repositories/bootstrap_repository.dart';
import 'repositories/chat_repository.dart';
import 'repositories/notifications_repository.dart';
import 'repositories/orders_repository.dart';
import 'repositories/profile_repository.dart';
import 'repositories/proposals_repository.dart';
import 'repositories/wallet_repository.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient.instance);

final bootstrapRepositoryProvider = Provider<BootstrapRepository>(
  (ref) => BootstrapRepository(ref.watch(apiClientProvider)),
);

final ordersRepositoryProvider = Provider<OrdersRepository>(
  (ref) => OrdersRepository(ref.watch(apiClientProvider)),
);

final notificationsRepositoryProvider = Provider<NotificationsRepository>(
  (ref) => NotificationsRepository(ref.watch(apiClientProvider)),
);

final proposalsRepositoryProvider = Provider<ProposalsRepository>(
  (ref) => ProposalsRepository(ref.watch(apiClientProvider)),
);

final chatRepositoryProvider = Provider<ChatRepository>(
  (ref) => ChatRepository(ref.watch(apiClientProvider)),
);

final walletRepositoryProvider = Provider<WalletRepository>(
  (ref) => WalletRepository(ref.watch(apiClientProvider)),
);

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(apiClientProvider)),
);

final blocksRepositoryProvider = Provider<BlocksRepository>(
  (ref) => BlocksRepository(ref.watch(apiClientProvider)),
);

/// App-wide bootstrap data (geo hierarchy, categories, feature flags) — same
/// role as the RN app's state.tsx context that every screen reads from
/// instead of each fetching /bootstrap itself.
final bootstrapProvider = FutureProvider<Bootstrap>((ref) async {
  final repo = ref.watch(bootstrapRepositoryProvider);
  return repo.fetchBootstrap();
});

/// "mode" is a pure view toggle (client vs. worker) — changes which orders
/// Home/Explore surface for the SAME logged-in account, never who the
/// account is. Mirrors frontend/src/state.tsx's Mode + persisted
/// "faze:mode" key exactly.
class ModeController extends StateNotifier<String> {
  ModeController() : super('client') {
    _hydrate();
  }

  static const _key = 'faze:mode';

  Future<void> _hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getString(_key) ?? 'client';
  }

  Future<void> setMode(String mode) async {
    state = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, mode);
  }
}

final modeControllerProvider = StateNotifierProvider<ModeController, String>((ref) => ModeController());

/// Unread notification count for Home's bell icon — refreshed on demand
/// (screen focus), mirrors frontend/src/state.tsx's refreshUnread().
class UnreadController extends StateNotifier<int> {
  UnreadController(this._repo) : super(0);
  final NotificationsRepository _repo;

  Future<void> refresh() async {
    try {
      state = await _repo.fetchUnreadCount();
    } catch (_) {
      // Keep last known count — same "swallow" behavior as the RN app's
      // bare .catch(() => {}) here.
    }
  }
}

final unreadControllerProvider = StateNotifierProvider<UnreadController, int>(
  (ref) => UnreadController(ref.watch(notificationsRepositoryProvider)),
);
