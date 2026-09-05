// Proves FASE 11 (in-app notifications) against the REAL backend, using a
// real notification-triggering action (a worker submitting a proposal —
// backend/routes/public.py's create_proposal calls notify() server-side)
// rather than a synthetic one.
//
//   flutter test test/notifications_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/notifications_repository.dart';
import 'package:fazum/core/repositories/orders_repository.dart';
import 'package:fazum/core/repositories/proposals_repository.dart';
import 'package:fazum/features/auth/data/auth_repository.dart';

String _randomPhone() {
  final rand = Random();
  final digits = List.generate(8, (_) => rand.nextInt(10)).join();
  return '949$digits';
}

void main() {
  ApiClient.instance.markAuthReady();

  test('a real proposal triggers a real notification, unread count and mark-read work', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Notif $tag',
      email: 'clientenotif_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase11!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    final notificationsRepo = NotificationsRepository(api);
    final initialUnread = await notificationsRepo.fetchUnreadCount();
    expect(initialUnread, 0);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Pedido para notificação $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 70,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Notif $tag',
      email: 'fazedornotif_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase11!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    await proposalsRepo.create(orderId: order.id, amount: 65, eta: 'hoje');

    // Back to the client — the worker's proposal should have notified them.
    api.setToken(clientReg.token);
    final unreadAfterProposal = await notificationsRepo.fetchUnreadCount();
    expect(unreadAfterProposal, greaterThanOrEqualTo(1));

    final notifications = await notificationsRepo.fetchNotifications();
    final proposalNotification = notifications.where((n) => n.type == 'proposal' && n.orderId == order.id);
    expect(proposalNotification, isNotEmpty);

    await notificationsRepo.markAllRead();
    final unreadAfterRead = await notificationsRepo.fetchUnreadCount();
    expect(unreadAfterRead, 0);
  });
}
