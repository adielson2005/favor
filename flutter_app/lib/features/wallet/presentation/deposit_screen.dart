import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/payment.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';

const _statusLabels = {
  'PENDING': 'Aguardando pagamento',
  'PROCESSING': 'Aguardando confirmação',
  'COMPLETED': 'Pagamento confirmado',
  'FAILED': 'O pagamento falhou',
  'REFUNDED': 'Estornado',
};

/// PIX deposit — POST /wallet/deposits creates a real ASAAS charge (see
/// backend/payments.py's AsaasProvider.create_pix_charge, wired to real
/// production credentials), shows the QR code + copia-e-cola it returns,
/// then polls GET /wallet/deposits/{id} until the ASAAS webhook
/// (routes/wallet.py's /webhooks/payment-provider) confirms it and credits
/// the wallet.
class DepositScreen extends ConsumerStatefulWidget {
  const DepositScreen({super.key});

  @override
  ConsumerState<DepositScreen> createState() => _DepositScreenState();
}

class _DepositScreenState extends ConsumerState<DepositScreen> {
  final _amount = TextEditingController();
  final _document = TextEditingController();
  bool _needsDocument = false;
  bool _submitting = false;
  bool _refreshing = false;
  Deposit? _deposit;
  Timer? _poll;

  @override
  void dispose() {
    _poll?.cancel();
    _amount.dispose();
    _document.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final value = double.tryParse(_amount.text.replaceAll(',', '.'));
    if (value == null || value <= 0) return;
    setState(() => _submitting = true);
    try {
      final document = _needsDocument ? _document.text.replaceAll(RegExp(r'\D'), '') : null;
      final deposit = await ref.read(walletRepositoryProvider).createDeposit(amount: value, document: document);
      if (!mounted) return;
      setState(() => _deposit = deposit);
      _startPolling();
    } on ApiException catch (e) {
      if (!mounted) return;
      // The backend's one distinguishing signal for "needs a CPF/CNPJ" is a
      // 400 whose message says so (routes/wallet.py's create_deposit) — no
      // separate error code, so this is the same check the message itself
      // is written to support.
      if (e.statusCode == 400 && e.message.toLowerCase().contains('cpf')) {
        setState(() => _needsDocument = true);
        return;
      }
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Não foi possível gerar o Pix'),
          content: Text(e.message),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _startPolling() {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 4), (_) => _refreshStatus());
  }

  Future<void> _refreshStatus() async {
    final current = _deposit;
    if (current == null || _refreshing) return;
    _refreshing = true;
    try {
      final updated = await ref.read(walletRepositoryProvider).fetchDeposit(current.id);
      if (!mounted) return;
      setState(() => _deposit = updated);
      if (updated.status != 'PROCESSING' && updated.status != 'PENDING') {
        _poll?.cancel();
      }
    } catch (_) {
      // Keep polling — a transient network blip shouldn't stop it.
    } finally {
      _refreshing = false;
    }
  }

  void _copyCode() {
    final payload = _deposit?.qrCodePayload;
    if (payload == null) return;
    Clipboard.setData(ClipboardData(text: payload));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Código Pix copiado.')));
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final deposit = _deposit;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              Expanded(child: Text('Depositar', style: theme.type.h2.copyWith(fontSize: 17))),
            ]),
          ),
          Expanded(child: deposit == null ? _buildForm(theme) : _buildQr(theme, deposit)),
        ]),
      ),
    );
  }

  Widget _buildForm(AppTheme theme) {
    final colors = theme.colors;
    final value = double.tryParse(_amount.text.replaceAll(',', '.'));
    final canSubmit = value != null && value > 0 && !_submitting && (!_needsDocument || _document.text.trim().isNotEmpty);

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Gere um Pix e o valor cai na sua carteira assim que o pagamento for confirmado.',
            style: theme.type.body.copyWith(color: colors.muted)),
        const SizedBox(height: 20),
        AppTextField(
          controller: _amount,
          theme: theme,
          label: 'Valor (R\$)',
          placeholder: '0,00',
          keyboardType: TextInputType.number,
          onChanged: (_) => setState(() {}),
        ),
        if (_needsDocument) ...[
          const SizedBox(height: 12),
          Text('Precisamos do seu CPF ou CNPJ pra gerar o primeiro Pix.',
              style: theme.type.small.copyWith(color: colors.muted)),
          const SizedBox(height: 8),
          AppTextField(
            controller: _document,
            theme: theme,
            label: 'CPF ou CNPJ',
            placeholder: 'Somente números',
            keyboardType: TextInputType.number,
            onChanged: (_) => setState(() {}),
          ),
        ],
        const SizedBox(height: 20),
        AppButton(
          title: _submitting ? 'Gerando...' : 'Gerar Pix',
          theme: theme,
          loading: _submitting,
          onPressed: canSubmit ? _submit : null,
        ),
      ],
    );
  }

  Widget _buildQr(AppTheme theme, Deposit deposit) {
    final colors = theme.colors;
    final status = deposit.status;
    final done = status != 'PROCESSING' && status != 'PENDING';
    final success = status == 'COMPLETED';

    if (done) {
      return Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(color: success ? colors.greenSoft : colors.dangerSoft, shape: BoxShape.circle),
            child: Icon(success ? Icons.check : Icons.close, size: 36, color: success ? colors.green : colors.danger),
          ),
          const SizedBox(height: 16),
          Text(_statusLabels[status] ?? status, style: theme.type.h1, textAlign: TextAlign.center),
          const SizedBox(height: 20),
          AppButton(title: 'Voltar para a carteira', theme: theme, onPressed: () => context.pop()),
        ]),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('R\$ ${deposit.amount.toStringAsFixed(2)}', style: theme.type.display, textAlign: TextAlign.center),
        const SizedBox(height: 4),
        Center(child: Text(_statusLabels[status] ?? status, style: theme.type.small.copyWith(color: colors.muted))),
        const SizedBox(height: 20),
        if (deposit.qrCodeImage != null)
          Center(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
              child: Image.memory(base64Decode(deposit.qrCodeImage!), width: 220, height: 220),
            ),
          ),
        const SizedBox(height: 20),
        if (deposit.qrCodePayload != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: colors.alt, borderRadius: BorderRadius.circular(12)),
            child: Text(
              deposit.qrCodePayload!,
              style: theme.type.micro.copyWith(color: colors.muted),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(height: 12),
          AppButton(title: 'Copiar código Pix', theme: theme, variant: AppButtonVariant.secondary, onPressed: _copyCode),
        ],
        const SizedBox(height: 20),
        Center(
          child: TextButton(
            onPressed: _refreshStatus,
            child: Text('Já paguei, atualizar status', style: TextStyle(color: colors.primary, fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }
}
