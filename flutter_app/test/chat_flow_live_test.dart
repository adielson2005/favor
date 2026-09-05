// Proves FASE 9's chat data layer end-to-end against the REAL backend — same
// standard as the other live tests. The UI's 4s polling itself isn't
// testable this way; what matters is that send/fetch actually round-trips
// through the real /orders/{id}/messages endpoints correctly.
//
//   flutter test test/chat_flow_live_test.dart --dart-define=API_BASE_URL=http://localhost:8000
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:fazum/core/networking/api_client.dart';
import 'package:fazum/core/repositories/chat_repository.dart';
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

  test('client and worker exchange messages on an accepted order', () async {
    final api = ApiClient.instance;
    final tag = DateTime.now().millisecondsSinceEpoch;

    final clientAuth = AuthRepository(api);
    final clientReg = await clientAuth.register(
      name: 'Cliente Chat $tag',
      email: 'clientechat_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase9!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'client',
      acceptTerms: true,
    );
    api.setToken(clientReg.token);

    final ordersRepo = OrdersRepository(api);
    final order = await ordersRepo.createOrder(
      title: 'Conversa de teste $tag',
      type: 'favor',
      categoryId: 'cat-casa',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      budget: 60,
    );

    final workerAuth = AuthRepository(api);
    final workerReg = await workerAuth.register(
      name: 'Fazedor Chat $tag',
      email: 'fazedorchat_$tag@example.com',
      phone: _randomPhone(),
      password: 'TesteFase9!23',
      cityId: 'city-parauapebas',
      neighborhoodId: 'nb-1',
      preference: 'worker',
      acceptTerms: true,
    );
    api.setToken(workerReg.token);
    await workerAuth.verifyEmail(workerReg.devCodeEmail!);
    await workerAuth.verifyPhone(workerReg.devCodePhone!);

    final proposalsRepo = ProposalsRepository(api);
    final proposal = await proposalsRepo.create(orderId: order.id, amount: 55, eta: 'hoje');

    api.setToken(clientReg.token);
    await proposalsRepo.accept(proposal.id);

    final chatRepo = ChatRepository(api);
    final sentByClient = await chatRepo.sendMessage(order.id, text: 'Oi! Pode vir às 15h?');
    expect(sentByClient.senderId, clientReg.user.id);
    expect(sentByClient.type, 'text');

    api.setToken(workerReg.token);
    final messagesForWorker = await chatRepo.fetchMessages(order.id);
    expect(messagesForWorker.any((m) => m.text == 'Oi! Pode vir às 15h?' && m.senderId == clientReg.user.id), isTrue);

    final sentByWorker = await chatRepo.sendMessage(order.id, text: 'Posso sim, chego às 15h.');
    expect(sentByWorker.senderId, workerReg.user.id);

    api.setToken(clientReg.token);
    final finalMessages = await chatRepo.fetchMessages(order.id);
    expect(finalMessages.length, greaterThanOrEqualTo(2));
    final texts = finalMessages.map((m) => m.text).toList();
    expect(texts.indexOf('Oi! Pode vir às 15h?') < texts.indexOf('Posso sim, chego às 15h.'), isTrue);
  });
}
