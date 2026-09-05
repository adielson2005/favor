import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/message.dart';
import '../../../core/models/order.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../auth/application/auth_controller.dart';

/// Mirrors frontend/app/chat/[id].tsx: near-real-time via 4s polling (not
/// WebSocket — same honest characterization used throughout this rewrite),
/// text + image messages, system messages, long-press to report a message,
/// and a "..." menu to report/block the other participant.
class ChatScreen extends ConsumerStatefulWidget {
  final String orderId;
  const ChatScreen({super.key, required this.orderId});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  Order? _order;
  List<ChatMessage> _messages = [];
  final _textController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _poll;
  bool _sending = false;
  String? _warning;

  @override
  void initState() {
    super.initState();
    _load();
    _poll = Timer.periodic(const Duration(seconds: 4), (_) => _load());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final ordersRepo = ref.read(ordersRepositoryProvider);
      final chatRepo = ref.read(chatRepositoryProvider);
      final results = await Future.wait([
        ordersRepo.fetchOrder(widget.orderId),
        chatRepo.fetchMessages(widget.orderId),
      ]);
      if (!mounted) return;
      final previousCount = _messages.length;
      setState(() {
        _order = results[0] as Order;
        _messages = results[1] as List<ChatMessage>;
      });
      if (_messages.length != previousCount) _scrollToEnd();
    } catch (_) {
      // Keep last known state — same as the RN screen's bare try/catch.
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send({String? imageB64}) async {
    final text = _textController.text.trim();
    if (imageB64 == null && text.isEmpty) return;
    _textController.clear();
    setState(() => _sending = true);
    try {
      final sent = await ref.read(chatRepositoryProvider).sendMessage(widget.orderId, text: text, imageB64: imageB64);
      setState(() => _warning = sent.warning);
      await _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _pickImage() async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: ImageSource.gallery, imageQuality: 40);
      if (picked == null) return;
      final bytes = await picked.readAsBytes();
      await _send(imageB64: 'data:image/jpeg;base64,${base64Encode(bytes)}');
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Não foi possível enviar a imagem: $e')));
    }
  }

  void _reportMessage(String messageId) {
    _showReasonPicker(
      title: 'Denunciar mensagem',
      onReasonPicked: (reason) => ref.read(chatRepositoryProvider).reportTarget(
            targetType: 'message',
            targetId: messageId,
            reason: reason,
          ),
    );
  }

  void _showReasonPicker({required String title, required Future<void> Function(String reason) onReasonPicked}) {
    const reasons = ['Spam', 'Conteúdo impróprio', 'Golpe ou fraude', 'Outro'];
    showModalBottomSheet(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(title, style: Theme.of(sheetContext).textTheme.titleMedium),
          ),
          ...reasons.map((reason) => ListTile(
                title: Text(reason),
                onTap: () async {
                  Navigator.pop(sheetContext);
                  try {
                    await onReasonPicked(reason);
                    if (!mounted) return;
                    ScaffoldMessenger.of(context)
                        .showSnackBar(const SnackBar(content: Text('Obrigado. Recebemos sua denúncia.')));
                  } on ApiException catch (e) {
                    if (!mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                  }
                },
              )),
        ]),
      ),
    );
  }

  void _openUserActions() {
    final me = ref.read(authControllerProvider).user;
    final order = _order;
    if (order == null || me == null) return;
    final other = order.clientId == me.id ? order.worker : order.client;
    if (other == null) return;

    showModalBottomSheet(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            leading: const Icon(Icons.flag_outlined),
            title: const Text('Denunciar usuário'),
            onTap: () {
              Navigator.pop(sheetContext);
              _showReasonPicker(
                title: 'Denunciar usuário',
                onReasonPicked: (reason) =>
                    ref.read(chatRepositoryProvider).reportTarget(targetType: 'user', targetId: other.id, reason: reason),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.block, color: Colors.red),
            title: const Text('Bloquear usuário', style: TextStyle(color: Colors.red)),
            onTap: () async {
              Navigator.pop(sheetContext);
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (dialogContext) => AlertDialog(
                  title: const Text('Bloquear usuário'),
                  content: const Text('Vocês não vão mais conseguir se contatar. Continuar?'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancelar')),
                    TextButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Bloquear')),
                  ],
                ),
              );
              if (confirmed != true) return;
              try {
                await ref.read(chatRepositoryProvider).blockUser(other.id);
                if (!mounted) return;
                context.pop();
              } on ApiException catch (e) {
                if (!mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
              }
            },
          ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final me = ref.watch(authControllerProvider).user;
    final order = _order;
    final other = order != null && me != null ? (order.clientId == me.id ? order.worker : order.client) : null;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            decoration: BoxDecoration(border: Border(bottom: BorderSide(color: colors.border))),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              AppAvatar(initials: other?.initials ?? '?', theme: theme, size: 38),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(other?.name ?? 'Conversa', style: theme.type.bodyStrong),
                  if (order != null)
                    Text('${order.title} · ${order.statusLabel}',
                        style: theme.type.small.copyWith(color: colors.muted), maxLines: 1, overflow: TextOverflow.ellipsis),
                ]),
              ),
              IconButton(
                onPressed: () => context.push('/order/${widget.orderId}'),
                icon: Icon(Icons.description_outlined, color: colors.primary),
              ),
              IconButton(onPressed: _openUserActions, icon: Icon(Icons.more_vert, color: colors.muted)),
            ]),
          ),
          Expanded(
            child: _messages.isEmpty
                ? Center(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.chat_bubble_outline, size: 30, color: colors.faint),
                      const SizedBox(height: 6),
                      Text('Comecem a combinar os detalhes.', style: theme.type.body.copyWith(color: colors.muted)),
                    ]),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(20),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      final message = _messages[index];
                      if (message.isSystem) {
                        return Center(
                          child: Container(
                            margin: const EdgeInsets.symmetric(vertical: 6),
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(color: colors.alt, borderRadius: BorderRadius.circular(12)),
                            child: Text(message.text, style: theme.type.small.copyWith(color: colors.muted)),
                          ),
                        );
                      }
                      final mine = me != null && message.senderId == me.id;
                      return Align(
                        alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                        child: GestureDetector(
                          onLongPress: () => _reportMessage(message.id),
                          child: ConstrainedBox(
                            constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              child: message.imageB64 != null
                                  ? ClipRRect(
                                      borderRadius: BorderRadius.circular(16),
                                      child: Image.memory(
                                        base64Decode(message.imageB64!.split(',').last),
                                        width: 200,
                                        height: 200,
                                        fit: BoxFit.cover,
                                      ),
                                    )
                                  : Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                      decoration: BoxDecoration(
                                        color: mine ? colors.primary : colors.surface,
                                        border: mine ? null : Border.all(color: colors.border),
                                        borderRadius: BorderRadius.only(
                                          topLeft: const Radius.circular(18),
                                          topRight: const Radius.circular(18),
                                          bottomLeft: Radius.circular(mine ? 18 : 5),
                                          bottomRight: Radius.circular(mine ? 5 : 18),
                                        ),
                                      ),
                                      child: Text(message.text,
                                          style: TextStyle(color: mine ? colors.onPrimary : colors.ink, fontSize: 14)),
                                    ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          if (_warning != null)
            InkWell(
              onTap: () => setState(() => _warning = null),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: colors.dangerSoft, borderRadius: BorderRadius.circular(12)),
                child: Row(children: [
                  Icon(Icons.error_outline, size: 16, color: colors.danger),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_warning!, style: theme.type.small.copyWith(color: colors.danger))),
                  Icon(Icons.close, size: 14, color: colors.danger),
                ]),
              ),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(border: Border(top: BorderSide(color: colors.border))),
            child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              IconButton(
                onPressed: _pickImage,
                icon: Icon(Icons.image_outlined, color: colors.muted),
                style: IconButton.styleFrom(backgroundColor: colors.alt),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _textController,
                  minLines: 1,
                  maxLines: 4,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Escreva uma mensagem...',
                    filled: true,
                    fillColor: colors.surface,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(22),
                      borderSide: BorderSide(color: colors.border),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: !_sending && _textController.text.trim().isNotEmpty ? () => _send() : null,
                icon: Icon(Icons.send, color: _textController.text.trim().isNotEmpty ? colors.onPrimary : colors.faint),
                style: IconButton.styleFrom(
                  backgroundColor: _textController.text.trim().isNotEmpty ? colors.primary : colors.alt,
                ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}
