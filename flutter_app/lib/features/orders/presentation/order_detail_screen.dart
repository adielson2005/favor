import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/order.dart';
import '../../../core/models/payment.dart';
import '../../../core/models/proposal.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../auth/application/auth_controller.dart';

/// Order detail screen — covers FASE 7 (Sistema de propostas: ver, comparar,
/// enviar, aceitar) and FASE 8 (Contratação: iniciar, concluir, cancelar),
/// mirroring the relevant slice of frontend/app/order/[id].tsx's state
/// machine. Chat, in-app payment, disputes, and reviews are still their own
/// later phases (9/10) and show the same honest "not built yet" affordance
/// the rest of the app uses, rather than a half-built flow.
class OrderDetailScreen extends ConsumerStatefulWidget {
  final String orderId;
  const OrderDetailScreen({super.key, required this.orderId});

  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  Order? _order;
  List<Proposal> _proposals = [];
  Payment? _payment;
  bool _loading = true;
  bool _acting = false;
  String? _error;

  // Worker's own proposal-submission form state.
  bool _showProposalForm = false;
  final _amount = TextEditingController();
  final _eta = TextEditingController();
  final _message = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _amount.dispose();
    _eta.dispose();
    _message.dispose();
    super.dispose();
  }

  bool get _isOwner {
    final me = ref.read(authControllerProvider).user;
    return me != null && _order != null && _order!.clientId == me.id;
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final ordersRepo = ref.read(ordersRepositoryProvider);
      final order = await ordersRepo.fetchOrder(widget.orderId);
      List<Proposal> proposals = [];
      try {
        proposals = await ref.read(proposalsRepositoryProvider).fetchForOrder(widget.orderId);
      } on ApiException {
        // Non-fatal — some viewers (e.g. anonymous) may not be allowed to
        // list proposals at all; the order itself still renders.
      }
      Payment? payment;
      if (order.status != 'published') {
        try {
          payment = await ref.read(walletRepositoryProvider).fetchOrderPayment(widget.orderId);
        } on ApiException {
          // Non-fatal — same reasoning as proposals above.
        }
      }
      if (!mounted) return;
      setState(() {
        _order = order;
        _proposals = proposals;
        _payment = payment;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _sendProposal() async {
    final amount = double.tryParse(_amount.text);
    if (amount == null || amount <= 0) return;
    setState(() => _acting = true);
    try {
      await ref.read(proposalsRepositoryProvider).create(
            orderId: widget.orderId,
            amount: amount,
            eta: _eta.text.trim(),
            message: _message.text.trim(),
          );
      setState(() => _showProposalForm = false);
      await _load();
    } on ApiException catch (e) {
      _showError('Não foi possível enviar a proposta', e.message);
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  Future<void> _cancelProposal(String proposalId) async {
    setState(() => _acting = true);
    try {
      await ref.read(proposalsRepositoryProvider).cancel(proposalId);
      await _load();
    } on ApiException catch (e) {
      _showError('Não foi possível cancelar', e.message);
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  Future<void> _acceptProposal(String proposalId) async {
    setState(() => _acting = true);
    try {
      await ref.read(proposalsRepositoryProvider).accept(proposalId);
      await _load();
    } on ApiException catch (e) {
      _showError('Não foi possível aceitar', e.message);
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  // ---------- lifecycle (FASE 8) ----------

  Future<void> _runLifecycleAction(Future<void> Function(String orderId) action, String failureTitle) async {
    setState(() => _acting = true);
    try {
      await action(widget.orderId);
      await _load();
    } on ApiException catch (e) {
      _showError(failureTitle, e.message);
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  Future<void> _start() => _runLifecycleAction(
      (id) => ref.read(ordersRepositoryProvider).start(id), 'Não foi possível iniciar o serviço');

  Future<void> _requestCompletion() => _runLifecycleAction(
      (id) => ref.read(ordersRepositoryProvider).requestCompletion(id), 'Não foi possível marcar como concluído');

  Future<void> _complete() => _runLifecycleAction(
      (id) => ref.read(ordersRepositoryProvider).complete(id), 'Não foi possível confirmar a conclusão');

  Future<void> _cancel() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Cancelar pedido?'),
        content: const Text('Isso não pode ser desfeito.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Voltar')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cancelar pedido')),
        ],
      ),
    );
    if (confirmed != true) return;
    await _runLifecycleAction((id) => ref.read(ordersRepositoryProvider).cancel(id), 'Não foi possível cancelar');
  }

  // ---------- payment (FASE 10) ----------

  /// Mirrors the RN app's payment-reauth pattern: try without a password
  /// first; the backend only asks for one (401, specific message) when its
  /// fraud check comes back MEDIUM risk — most payments never hit this.
  Future<void> _pay({String? password}) async {
    setState(() => _acting = true);
    try {
      final payment = await ref.read(walletRepositoryProvider).payOrder(widget.orderId, password: password);
      if (!mounted) return;
      setState(() => _payment = payment);
    } on ApiException catch (e) {
      if (e.isUnauthorized && password == null) {
        if (mounted) setState(() => _acting = false);
        _promptPasswordAndPay();
        return;
      }
      _showError('Não foi possível pagar', e.message);
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  void _promptPasswordAndPay() {
    final passwordController = TextEditingController();
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirme sua senha'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('Por segurança, confirme sua senha para concluir este pagamento.'),
          const SizedBox(height: 12),
          TextField(controller: passwordController, obscureText: true, autofocus: true),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _pay(password: passwordController.text);
            },
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }

  void _showError(String title, String message) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final me = ref.watch(authControllerProvider).user;

    return Scaffold(
      backgroundColor: colors.bg,
      appBar: AppBar(
        backgroundColor: colors.bg,
        elevation: 0,
        iconTheme: IconThemeData(color: colors.ink),
        title: Text('Pedido', style: theme.type.h2.copyWith(fontSize: 16)),
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(child: Text(_error!, style: theme.type.body.copyWith(color: colors.danger)))
                : _order == null
                    ? const SizedBox()
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: ListView(
                          padding: const EdgeInsets.all(20),
                          children: [
                            _buildOrderCard(theme),
                            const SizedBox(height: 24),
                            if (_order!.status == 'published') ...[
                              if (_isOwner)
                                _buildProposalsForOwner(theme)
                              else if (me != null)
                                _buildProposalFormForWorker(theme),
                            ] else
                              _buildLifecycleSection(theme),
                          ],
                        ),
                      ),
      ),
    );
  }

  Widget _buildOrderCard(AppTheme theme) {
    final colors = theme.colors;
    final order = _order!;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: colors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(order.title, style: theme.type.h2)),
          Text('R\$ ${order.budget.toStringAsFixed(0)}',
              style: theme.type.bodyStrong.copyWith(color: colors.green)),
        ]),
        const SizedBox(height: 8),
        Text(order.description, style: theme.type.body.copyWith(color: colors.muted)),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 6, children: [
          _Tag(icon: Icons.category_outlined, text: order.category.name, theme: theme),
          if ((order.neighborhood ?? order.city) != null)
            _Tag(icon: Icons.location_on_outlined, text: order.neighborhood ?? order.city!, theme: theme),
          _Tag(icon: Icons.access_time, text: order.dateLabel, theme: theme),
          if (order.urgent) _Tag(icon: Icons.bolt, text: 'Urgente', theme: theme, color: colors.danger),
        ]),
        const SizedBox(height: 8),
        Text(order.statusLabel, style: theme.type.small.copyWith(color: colors.primary, fontWeight: FontWeight.bold)),
      ]),
    );
  }

  /// FASE 8: status-driven actions. Mirrors backend/routes/public.py's role
  /// checks exactly (worker starts/requests-completion, client
  /// completes/cancels) — the buttons shown here are a UI convenience, the
  /// backend is the actual authority and would reject a call from the wrong
  /// role or the wrong status regardless of what this screen shows.
  Widget _buildLifecycleSection(AppTheme theme) {
    final colors = theme.colors;
    final order = _order!;
    final me = ref.read(authControllerProvider).user;
    final isWorker = me != null && order.workerId == me.id;

    final steps = <Widget>[];

    // Chat (FASE 9) opens for either side once a worker is assigned —
    // mirrors frontend/app/chat/[id].tsx, which never gates on order status,
    // only on the caller being the order's client or worker.
    if (order.workerId != null && (isWorker || _isOwner)) {
      steps.add(AppButton(
        title: 'Conversar',
        theme: theme,
        variant: AppButtonVariant.secondary,
        onPressed: () => context.push('/chat/${order.id}'),
      ));
      steps.add(const SizedBox(height: 12));
    }

    switch (order.status) {
      case 'accepted':
        if (isWorker) {
          if (_payment == null) {
            steps.add(Text('Aguardando o pagamento de quem pediu.', style: theme.type.body.copyWith(color: colors.muted)));
            steps.add(const SizedBox(height: 12));
          }
          steps.add(AppButton(title: 'Iniciar serviço', theme: theme, loading: _acting, onPressed: _acting ? null : _start));
        } else if (_isOwner) {
          if (_payment == null) {
            steps.add(AppButton(
              title: 'Pagar agora',
              theme: theme,
              loading: _acting,
              onPressed: _acting ? null : () => _pay(),
            ));
          } else {
            steps.add(Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: colors.greenSoft, borderRadius: BorderRadius.circular(14)),
              child: Row(children: [
                Icon(Icons.check_circle_outline, size: 18, color: colors.green),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('Pago — R\$ ${_payment!.grossAmount.toStringAsFixed(2)} protegido até a conclusão.',
                      style: theme.type.small.copyWith(color: colors.ink)),
                ),
              ]),
            ));
            steps.add(const SizedBox(height: 12));
            steps.add(Text('Aguardando o fazedor iniciar o serviço.', style: theme.type.body.copyWith(color: colors.muted)));
          }
          steps.add(const SizedBox(height: 12));
          steps.add(AppButton(
            title: 'Cancelar pedido',
            theme: theme,
            variant: AppButtonVariant.danger,
            loading: _acting,
            onPressed: _acting ? null : _cancel,
          ));
        }
      case 'in_progress':
        if (isWorker) {
          steps.add(AppButton(
              title: 'Marcar como concluído', theme: theme, loading: _acting, onPressed: _acting ? null : _requestCompletion));
        } else if (_isOwner) {
          steps.add(Text('O serviço está em andamento.', style: theme.type.body.copyWith(color: colors.muted)));
          steps.add(const SizedBox(height: 12));
          steps.add(AppButton(title: 'Confirmar conclusão', theme: theme, loading: _acting, onPressed: _acting ? null : _complete));
        }
      case 'completion_requested':
        if (_isOwner) {
          steps.add(Text('O fazedor marcou como concluído — confirme para liberar.',
              style: theme.type.body.copyWith(color: colors.muted)));
          steps.add(const SizedBox(height: 12));
          steps.add(AppButton(title: 'Confirmar conclusão', theme: theme, loading: _acting, onPressed: _acting ? null : _complete));
        } else if (isWorker) {
          steps.add(Text('Aguardando quem pediu confirmar a conclusão.', style: theme.type.body.copyWith(color: colors.muted)));
        }
      case 'completed':
        steps.add(Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: colors.greenSoft, borderRadius: BorderRadius.circular(16)),
          child: Row(children: [
            Icon(Icons.check_circle, color: colors.green, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text('Serviço concluído. Avaliação ainda não foi construída nesta fase.',
                  style: theme.type.small.copyWith(color: colors.ink)),
            ),
          ]),
        ));
      case 'cancelled':
        steps.add(Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: colors.dangerSoft, borderRadius: BorderRadius.circular(16)),
          child: Text('Este pedido foi cancelado.', style: theme.type.small.copyWith(color: colors.danger)),
        ));
    }

    if (steps.isEmpty) {
      steps.add(Text('Status: ${order.statusLabel}', style: theme.type.body.copyWith(color: colors.muted)));
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: steps);
  }

  Widget _buildProposalsForOwner(AppTheme theme) {
    final colors = theme.colors;
    if (_proposals.isEmpty) {
      return Text('Ainda não chegaram propostas para este pedido.',
          style: theme.type.body.copyWith(color: colors.muted));
    }
    final sorted = [..._proposals]..sort((a, b) => a.amount.compareTo(b.amount));
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Propostas (${sorted.length})', style: theme.type.h2.copyWith(fontSize: 17)),
      const SizedBox(height: 12),
      ...sorted.map((p) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _ProposalCard(
              proposal: p,
              theme: theme,
              showAcceptAction: p.status == 'pending',
              acting: _acting,
              onAccept: () => _acceptProposal(p.id),
            ),
          )),
    ]);
  }

  Widget _buildProposalFormForWorker(AppTheme theme) {
    final colors = theme.colors;
    final myProposal = _proposals.where((p) => p.workerId == ref.read(authControllerProvider).user?.id).firstOrNull;

    if (myProposal != null) {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Sua proposta', style: theme.type.h2.copyWith(fontSize: 17)),
        const SizedBox(height: 12),
        _ProposalCard(proposal: myProposal, theme: theme, showAcceptAction: false, acting: false, onAccept: () {}),
        if (myProposal.status == 'pending') ...[
          const SizedBox(height: 12),
          AppButton(
            title: 'Cancelar proposta',
            theme: theme,
            variant: AppButtonVariant.danger,
            loading: _acting,
            onPressed: _acting ? null : () => _cancelProposal(myProposal.id),
          ),
        ],
      ]);
    }

    if (!_showProposalForm) {
      return AppButton(
        title: 'Enviar proposta',
        theme: theme,
        onPressed: () => setState(() => _showProposalForm = true),
      );
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: colors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Sua proposta', style: theme.type.h2.copyWith(fontSize: 16)),
        const SizedBox(height: 12),
        AppTextField(
          controller: _amount,
          theme: theme,
          label: 'Valor (R\$)',
          placeholder: '0',
          keyboardType: TextInputType.number,
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 10),
        AppTextField(controller: _eta, theme: theme, label: 'Prazo', placeholder: 'Ex: hoje à tarde'),
        const SizedBox(height: 10),
        AppTextField(controller: _message, theme: theme, label: 'Mensagem (opcional)', placeholder: 'Diga por que você é a pessoa certa'),
        const SizedBox(height: 16),
        AppButton(
          title: 'Enviar proposta',
          theme: theme,
          loading: _acting,
          onPressed: (double.tryParse(_amount.text) ?? 0) > 0 && !_acting ? _sendProposal : null,
        ),
      ]),
    );
  }
}

class _Tag extends StatelessWidget {
  final IconData icon;
  final String text;
  final AppTheme theme;
  final Color? color;
  const _Tag({required this.icon, required this.text, required this.theme, this.color});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final c = color ?? colors.muted;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 14, color: c),
      const SizedBox(width: 4),
      Text(text, style: TextStyle(color: c, fontSize: 12)),
    ]);
  }
}

class _ProposalCard extends StatelessWidget {
  final Proposal proposal;
  final AppTheme theme;
  final bool showAcceptAction;
  final bool acting;
  final VoidCallback onAccept;

  const _ProposalCard({
    required this.proposal,
    required this.theme,
    required this.showAcceptAction,
    required this.acting,
    required this.onAccept,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    final worker = proposal.worker;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: colors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: GestureDetector(
              onTap: worker != null ? () => context.push('/user/${worker.id}') : null,
              child: Row(children: [
                if (worker != null) ...[
                  AppAvatar(initials: worker.initials, theme: theme, size: 36),
                  const SizedBox(width: 10),
                ],
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(worker?.name ?? 'Prestador', style: theme.type.bodyStrong),
                    if (worker != null)
                      Row(children: [
                        Icon(Icons.star, size: 13, color: colors.amber),
                        const SizedBox(width: 2),
                        Text('${worker.rating.toStringAsFixed(1)} · ${worker.jobsDone} trabalhos',
                            style: theme.type.small.copyWith(color: colors.muted)),
                      ]),
                  ]),
                ),
              ]),
            ),
          ),
          Text('R\$ ${proposal.amount.toStringAsFixed(0)}',
              style: theme.type.bodyStrong.copyWith(color: colors.green)),
        ]),
        if (proposal.eta.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text('Prazo: ${proposal.eta}', style: theme.type.small.copyWith(color: colors.muted)),
        ],
        if (proposal.message.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(proposal.message, style: theme.type.small.copyWith(color: colors.muted)),
        ],
        Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(proposal.status, style: theme.type.micro.copyWith(color: colors.faint)),
        ),
        if (showAcceptAction) ...[
          const SizedBox(height: 10),
          AppButton(title: 'Aceitar proposta', theme: theme, loading: acting, onPressed: acting ? null : onAccept),
        ],
      ]),
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
