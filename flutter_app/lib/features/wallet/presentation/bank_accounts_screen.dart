import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/bank_account.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/empty_state.dart';

/// Mirrors frontend/app/wallet/bank-accounts.tsx: list, add (bottom sheet
/// form), set primary, remove (password-confirmed). Same fields as
/// backend/models.py's BankAccountIn — holder_name, document, bank_code,
/// agency, account_number, account_type, password — no bank picker, same
/// free-text bank_code field the RN screen uses.
class BankAccountsScreen extends ConsumerStatefulWidget {
  const BankAccountsScreen({super.key});

  @override
  ConsumerState<BankAccountsScreen> createState() => _BankAccountsScreenState();
}

class _BankAccountsScreenState extends ConsumerState<BankAccountsScreen> {
  List<BankAccount> _accounts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final accounts = await ref.read(walletRepositoryProvider).fetchBankAccounts();
      if (mounted) setState(() => _accounts = accounts);
    } catch (_) {
      // Keep last known state.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _setPrimary(String id) async {
    try {
      await ref.read(walletRepositoryProvider).setPrimaryBankAccount(id);
      await _load();
    } on ApiException catch (e) {
      _showSnack(e.message);
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  void _confirmRemove(BankAccount account) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Remover conta'),
        content: Text('Remover a conta terminada em ${account.accountNumberMasked}? Essa ação é definitiva.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _promptPasswordAndRemove(account.id);
            },
            child: const Text('Remover'),
          ),
        ],
      ),
    );
  }

  void _promptPasswordAndRemove(String accountId) {
    final passwordController = TextEditingController();
    var removing = false;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) => Padding(
          padding: EdgeInsets.only(
            left: 20,
            right: 20,
            top: 20,
            bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Confirmar senha', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 8),
            const Text('Por segurança, confirme sua senha para remover esta conta.'),
            const SizedBox(height: 12),
            TextField(controller: passwordController, obscureText: true, autofocus: true),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: passwordController.text.isEmpty || removing
                    ? null
                    : () async {
                        setSheetState(() => removing = true);
                        try {
                          await ref
                              .read(walletRepositoryProvider)
                              .removeBankAccount(accountId, password: passwordController.text);
                          if (sheetContext.mounted) Navigator.pop(sheetContext);
                          await _load();
                        } on ApiException catch (e) {
                          setSheetState(() => removing = false);
                          _showSnack(e.message);
                        }
                      },
                child: Text(removing ? 'Removendo...' : 'Remover conta'),
              ),
            ),
          ]),
        ),
      ),
    );
  }

  void _openAddForm() {
    final holderName = TextEditingController();
    final document = TextEditingController();
    final bankCode = TextEditingController();
    final agency = TextEditingController();
    final accountNumber = TextEditingController();
    final password = TextEditingController();
    var saving = false;
    String? error;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          bool canSave() =>
              holderName.text.trim().isNotEmpty &&
              document.text.trim().isNotEmpty &&
              bankCode.text.trim().isNotEmpty &&
              agency.text.trim().isNotEmpty &&
              accountNumber.text.trim().isNotEmpty &&
              password.text.isNotEmpty &&
              !saving;

          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: SingleChildScrollView(
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Adicionar conta', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(height: 16),
                AppTextField(
                  controller: holderName,
                  theme: theme,
                  label: 'Nome do titular',
                  onChanged: (_) => setSheetState(() {}),
                ),
                const SizedBox(height: 10),
                AppTextField(
                  controller: document,
                  theme: theme,
                  label: 'CPF ou CNPJ',
                  keyboardType: TextInputType.number,
                  onChanged: (_) => setSheetState(() {}),
                ),
                const SizedBox(height: 10),
                Row(children: [
                  Expanded(
                    child: AppTextField(
                      controller: bankCode,
                      theme: theme,
                      label: 'Banco',
                      placeholder: '001',
                      onChanged: (_) => setSheetState(() {}),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: AppTextField(
                      controller: agency,
                      theme: theme,
                      label: 'Agência',
                      onChanged: (_) => setSheetState(() {}),
                    ),
                  ),
                ]),
                const SizedBox(height: 10),
                AppTextField(
                  controller: accountNumber,
                  theme: theme,
                  label: 'Conta',
                  onChanged: (_) => setSheetState(() {}),
                ),
                const SizedBox(height: 10),
                AppTextField(
                  controller: password,
                  theme: theme,
                  label: 'Confirme sua senha',
                  obscureText: true,
                  onChanged: (_) => setSheetState(() {}),
                ),
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Text(error!, style: TextStyle(color: theme.colors.danger, fontSize: 12)),
                ],
                const SizedBox(height: 16),
                AppButton(
                  title: 'Adicionar',
                  theme: theme,
                  loading: saving,
                  onPressed: canSave()
                      ? () async {
                          setSheetState(() {
                            saving = true;
                            error = null;
                          });
                          try {
                            await ref.read(walletRepositoryProvider).addBankAccount(
                                  holderName: holderName.text.trim(),
                                  document: document.text.replaceAll(RegExp(r'\D'), ''),
                                  bankCode: bankCode.text.trim(),
                                  agency: agency.text.trim(),
                                  accountNumber: accountNumber.text.trim(),
                                  password: password.text,
                                );
                            if (sheetContext.mounted) Navigator.pop(sheetContext);
                            await _load();
                          } on ApiException catch (e) {
                            setSheetState(() {
                              saving = false;
                              error = e.message;
                            });
                          }
                        }
                      : null,
                ),
              ]),
            ),
          );
        },
      ),
    );
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
              Expanded(child: Text('Contas para saque', style: theme.type.h2.copyWith(fontSize: 17))),
              IconButton(onPressed: _openAddForm, icon: Icon(Icons.add_circle, color: colors.primary, size: 26)),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _accounts.isEmpty
                    ? Center(
                        child: EmptyState(
                          icon: Icons.credit_card_outlined,
                          title: 'Nenhuma conta cadastrada.',
                          body: 'Adicione uma conta bancária para poder sacar seus ganhos.',
                          actionTitle: 'Adicionar conta',
                          onAction: _openAddForm,
                          theme: theme,
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.all(20),
                        children: _accounts
                            .map((acc) => Container(
                                  margin: const EdgeInsets.only(bottom: 12),
                                  padding: const EdgeInsets.all(16),
                                  decoration: BoxDecoration(
                                    color: colors.surface,
                                    border: Border.all(color: colors.border),
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Row(children: [
                                      Icon(Icons.credit_card_outlined, size: 18, color: colors.primary),
                                      const SizedBox(width: 8),
                                      Expanded(child: Text(acc.holderName, style: theme.type.bodyStrong)),
                                      if (acc.isPrimary)
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                          decoration:
                                              BoxDecoration(color: colors.primarySoft, borderRadius: BorderRadius.circular(999)),
                                          child: Text('Principal',
                                              style: TextStyle(color: colors.primary, fontSize: 11, fontWeight: FontWeight.bold)),
                                        ),
                                    ]),
                                    const SizedBox(height: 6),
                                    Text('Banco ${acc.bankCode} · Ag ${acc.agency} · Conta ${acc.accountNumberMasked}',
                                        style: theme.type.small.copyWith(color: colors.muted)),
                                    Text(acc.documentMasked, style: theme.type.micro.copyWith(color: colors.faint)),
                                    const SizedBox(height: 8),
                                    Row(children: [
                                      if (!acc.isPrimary)
                                        TextButton(
                                          onPressed: () => _setPrimary(acc.id),
                                          child: Text('Definir como principal',
                                              style: TextStyle(color: colors.primary, fontWeight: FontWeight.bold, fontSize: 13)),
                                        ),
                                      TextButton(
                                        onPressed: () => _confirmRemove(acc),
                                        child: Text('Remover',
                                            style: TextStyle(color: colors.danger, fontWeight: FontWeight.bold, fontSize: 13)),
                                      ),
                                    ]),
                                  ]),
                                ))
                            .toList(),
                      ),
          ),
        ]),
      ),
    );
  }
}
