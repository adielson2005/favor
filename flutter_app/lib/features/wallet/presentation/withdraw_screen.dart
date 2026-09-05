import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/bank_account.dart';
import '../../../core/models/wallet.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/empty_state.dart';

const _statusLabels = {
  'PENDING': 'Em processamento',
  'PROCESSING': 'Processando',
  'COMPLETED': 'Concluído',
  'FAILED': 'Recusado',
  'CANCELLED': 'Cancelado',
  'REVIEW_REQUIRED': 'Em análise',
};

/// Mirrors frontend/app/wallet/withdraw.tsx: pick a bank account (defaults
/// to the primary one), amount, password, submit — same idempotency-key
/// protection as every other financial POST in this app.
class WithdrawScreen extends ConsumerStatefulWidget {
  const WithdrawScreen({super.key});

  @override
  ConsumerState<WithdrawScreen> createState() => _WithdrawScreenState();
}

class _WithdrawScreenState extends ConsumerState<WithdrawScreen> {
  WalletBalance? _wallet;
  List<BankAccount> _accounts = [];
  String? _selectedAccountId;
  final _amount = TextEditingController();
  final _password = TextEditingController();
  bool _loading = true;
  bool _submitting = false;
  String? _doneStatus;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _amount.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(walletRepositoryProvider);
      final results = await Future.wait([repo.fetchWallet(), repo.fetchBankAccounts()]);
      if (!mounted) return;
      final accounts = results[1] as List<BankAccount>;
      final primary = accounts.where((a) => a.isPrimary).firstOrNull ?? accounts.firstOrNull;
      setState(() {
        _wallet = results[0] as WalletBalance;
        _accounts = accounts;
        _selectedAccountId = primary?.id;
      });
    } catch (_) {
      // Keep last known state.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    final value = double.tryParse(_amount.text.replaceAll(',', '.'));
    if (_selectedAccountId == null || value == null || value <= 0 || _password.text.isEmpty) return;
    setState(() => _submitting = true);
    try {
      final result = await ref.read(walletRepositoryProvider).requestWithdrawal(
            amount: value,
            bankAccountId: _selectedAccountId!,
            password: _password.text,
          );
      if (!mounted) return;
      setState(() => _doneStatus = result.status);
    } on ApiException catch (e) {
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Não foi possível sacar'),
          content: Text(e.message),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
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
              Expanded(child: Text('Sacar', style: theme.type.h2.copyWith(fontSize: 17))),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _doneStatus != null
                    ? _buildDone(theme)
                    : _accounts.isEmpty
                        ? Center(
                            child: EmptyState(
                              icon: Icons.credit_card_outlined,
                              title: 'Adicione uma conta bancária antes de sacar.',
                              actionTitle: 'Adicionar conta',
                              onAction: () => context.push('/wallet/bank-accounts'),
                              theme: theme,
                            ),
                          )
                        : _buildForm(theme),
          ),
        ]),
      ),
    );
  }

  Widget _buildDone(AppTheme theme) {
    final colors = theme.colors;
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(color: colors.greenSoft, shape: BoxShape.circle),
          child: Icon(Icons.check, size: 36, color: colors.green),
        ),
        const SizedBox(height: 16),
        Text('Saque solicitado.', style: theme.type.h1, textAlign: TextAlign.center),
        const SizedBox(height: 8),
        Text(_statusLabels[_doneStatus] ?? _doneStatus!, style: theme.type.body.copyWith(color: colors.muted)),
        const SizedBox(height: 20),
        AppButton(title: 'Voltar para a carteira', theme: theme, onPressed: () => context.pop()),
      ]),
    );
  }

  Widget _buildForm(AppTheme theme) {
    final colors = theme.colors;
    final wallet = _wallet;
    final value = double.tryParse(_amount.text.replaceAll(',', '.'));
    final canSubmit = _selectedAccountId != null && value != null && value > 0 && _password.text.isNotEmpty && !_submitting;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (wallet != null)
          Text('Saldo disponível: R\$ ${wallet.available.toStringAsFixed(2)}',
              style: theme.type.body.copyWith(color: colors.muted)),
        const SizedBox(height: 16),
        Text('CONTA', style: theme.type.micro.copyWith(color: colors.muted)),
        const SizedBox(height: 8),
        RadioGroup<String>(
          groupValue: _selectedAccountId,
          onChanged: (v) => setState(() => _selectedAccountId = v),
          child: Column(
            children: _accounts
                .map((acc) => RadioListTile<String>(
                      value: acc.id,
                      title: Text('${acc.holderName} — ${acc.accountNumberMasked}'),
                      subtitle: Text('Banco ${acc.bankCode} · Ag ${acc.agency}'),
                      contentPadding: EdgeInsets.zero,
                    ))
                .toList(),
          ),
        ),
        const SizedBox(height: 8),
        AppTextField(
          controller: _amount,
          theme: theme,
          label: 'Valor (R\$)',
          placeholder: '0,00',
          keyboardType: TextInputType.number,
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        AppTextField(
          controller: _password,
          theme: theme,
          label: 'Confirme sua senha',
          obscureText: true,
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 20),
        AppButton(
          title: _submitting ? 'Enviando...' : 'Confirmar saque',
          theme: theme,
          loading: _submitting,
          onPressed: canSubmit ? _submit : null,
        ),
      ],
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
