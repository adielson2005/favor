import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/providers.dart';
import '../../../core/repositories/blocks_repository.dart';
import '../../../core/services/google_auth_service.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../auth/application/auth_controller.dart';

/// Mirrors frontend/app/security.tsx: verification status, connected
/// accounts, change-email/change-phone (both require the current password
/// and hand back a fresh session token — see AuthRepository.changeEmail's
/// doc), quick links into wallet, and blocked users.
///
/// "Google" row calls the real POST /auth/google/link once tapped — there's
/// no GET endpoint yet to report whether an account already has Google
/// linked, so the row's label stays "Não conectado" even after a successful
/// link this session (a real but narrower gap than the fully-stubbed button
/// this used to be).
class SecurityScreen extends ConsumerStatefulWidget {
  const SecurityScreen({super.key});

  @override
  ConsumerState<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends ConsumerState<SecurityScreen> {
  List<BlockedUser>? _blocks;
  bool _googleLinked = false;
  bool _linkingGoogle = false;

  @override
  void initState() {
    super.initState();
    _loadBlocks();
  }

  Future<void> _loadBlocks() async {
    try {
      final blocks = await ref.read(blocksRepositoryProvider).listBlocks();
      if (mounted) setState(() => _blocks = blocks);
    } on ApiException {
      if (mounted) setState(() => _blocks = []);
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _pressGoogle() async {
    if (_linkingGoogle || _googleLinked) return;
    setState(() => _linkingGoogle = true);
    try {
      final google = await GoogleAuthService.instance.signIn();
      await ref.read(authControllerProvider.notifier).linkGoogle(idToken: google.idToken, nonce: google.nonce);
      if (mounted) setState(() => _googleLinked = true);
      _showSnack('Conta Google vinculada.');
    } on GoogleAuthException catch (e) {
      if (!e.cancelled) _showSnack(e.message);
    } on ApiException catch (e) {
      _showSnack(e.message);
    } finally {
      if (mounted) setState(() => _linkingGoogle = false);
    }
  }

  void _openChangeEmail() {
    final email = TextEditingController();
    final password = TextEditingController();
    var saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          final canSave = email.text.trim().isNotEmpty && password.text.isNotEmpty && !saving;
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Alterar e-mail', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              AppTextField(
                controller: email,
                theme: theme,
                label: 'Novo e-mail',
                placeholder: 'voce@email.com',
                onChanged: (_) => setSheetState(() {}),
              ),
              const SizedBox(height: 10),
              AppTextField(
                controller: password,
                theme: theme,
                label: 'Senha atual',
                obscureText: true,
                onChanged: (_) => setSheetState(() {}),
              ),
              const SizedBox(height: 16),
              AppButton(
                title: 'Salvar',
                theme: theme,
                loading: saving,
                onPressed: canSave
                    ? () async {
                        setSheetState(() => saving = true);
                        try {
                          await ref.read(authControllerProvider.notifier).changeEmail(
                                email: email.text.trim().toLowerCase(),
                                password: password.text,
                              );
                          if (sheetContext.mounted) Navigator.pop(sheetContext);
                          if (mounted) context.push('/auth/verify-email');
                        } on ApiException catch (e) {
                          setSheetState(() => saving = false);
                          _showSnack('Não foi possível alterar o e-mail: ${e.message}');
                        }
                      }
                    : null,
              ),
            ]),
          );
        },
      ),
    );
  }

  void _openChangePhone() {
    final phone = TextEditingController();
    final password = TextEditingController();
    var saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          final me = ref.read(authControllerProvider).user;
          final hasPhone = (me?.phone ?? '').isNotEmpty;
          final canSave =
              phone.text.replaceAll(RegExp(r'\D'), '').length >= 10 && (!hasPhone || password.text.isNotEmpty) && !saving;
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Alterar telefone', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              AppTextField(
                controller: phone,
                theme: theme,
                label: 'Novo telefone',
                placeholder: '(94) 99999-9999',
                keyboardType: TextInputType.phone,
                onChanged: (v) {
                  final formatted = _formatPhoneBR(v);
                  if (formatted != v) {
                    phone.value = TextEditingValue(
                      text: formatted,
                      selection: TextSelection.collapsed(offset: formatted.length),
                    );
                  }
                  setSheetState(() {});
                },
              ),
              if (hasPhone) ...[
                const SizedBox(height: 10),
                AppTextField(
                  controller: password,
                  theme: theme,
                  label: 'Senha atual',
                  obscureText: true,
                  onChanged: (_) => setSheetState(() {}),
                ),
              ],
              const SizedBox(height: 16),
              AppButton(
                title: 'Salvar',
                theme: theme,
                loading: saving,
                onPressed: canSave
                    ? () async {
                        setSheetState(() => saving = true);
                        try {
                          await ref.read(authControllerProvider.notifier).changePhone(
                                phone: phone.text.replaceAll(RegExp(r'\D'), ''),
                                password: hasPhone ? password.text : null,
                              );
                          if (sheetContext.mounted) Navigator.pop(sheetContext);
                          if (mounted) context.push('/auth/verify-phone');
                        } on ApiException catch (e) {
                          setSheetState(() => saving = false);
                          _showSnack('Não foi possível alterar o telefone: ${e.message}');
                        }
                      }
                    : null,
              ),
            ]),
          );
        },
      ),
    );
  }

  static String _formatPhoneBR(String raw) {
    final digits = raw.replaceAll(RegExp(r'\D'), '');
    final d = digits.length > 11 ? digits.substring(0, 11) : digits;
    if (d.length <= 2) return d;
    if (d.length <= 7) return '(${d.substring(0, 2)}) ${d.substring(2)}';
    return '(${d.substring(0, 2)}) ${d.substring(2, 7)}-${d.substring(7)}';
  }

  void _confirmUnblock(BlockedUser block) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Desbloquear usuário'),
        content: const Text('Vocês voltam a poder se contatar. Continuar?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancelar')),
          TextButton(
            onPressed: () async {
              Navigator.pop(dialogContext);
              try {
                await ref.read(blocksRepositoryProvider).unblock(block.blockedUserId);
                if (mounted) setState(() => _blocks = _blocks!.where((b) => b.blockedUserId != block.blockedUserId).toList());
              } on ApiException {
                if (mounted) _showSnack('Não conseguimos desbloquear agora.');
              }
            },
            child: const Text('Desbloquear'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final me = ref.watch(authControllerProvider).user;

    if (me == null) return Scaffold(backgroundColor: colors.bg);

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              const SizedBox(width: 6),
              Text('Segurança', style: theme.type.h2.copyWith(fontSize: 18)),
            ]),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                _SecuritySection(title: 'Conta', theme: theme, children: [
                  _StatusRow(
                    icon: Icons.mail_outline,
                    label: 'E-mail verificado',
                    ok: me.verifiedEmail,
                    theme: theme,
                    onTap: me.verifiedEmail ? null : () => context.push('/auth/verify-email'),
                  ),
                  _StatusRow(
                    icon: Icons.call_outlined,
                    label: 'Telefone verificado',
                    ok: me.verifiedPhone,
                    theme: theme,
                    onTap: me.verifiedPhone ? null : () => context.push('/auth/verify-phone'),
                  ),
                  _StatusRow(icon: Icons.verified_user_outlined, label: 'Identidade verificada', ok: me.verifiedIdentity, theme: theme),
                ]),
                _SecuritySection(title: 'Contas conectadas', theme: theme, children: [
                  _ProfileRow(
                    icon: Icons.g_mobiledata,
                    label: 'Google',
                    value: _googleLinked ? 'Conectado' : 'Não conectado',
                    theme: theme,
                    onTap: _googleLinked ? null : _pressGoogle,
                  ),
                ]),
                _SecuritySection(title: 'Acesso', theme: theme, children: [
                  _ProfileRow(icon: Icons.lock_outline, label: 'Alterar senha', theme: theme, onTap: () => context.push('/profile')),
                  _ProfileRow(icon: Icons.mail_outline, label: 'Alterar e-mail', theme: theme, onTap: _openChangeEmail),
                  _ProfileRow(icon: Icons.call_outlined, label: 'Alterar telefone', theme: theme, onTap: _openChangePhone),
                ]),
                _SecuritySection(title: 'Dados financeiros', theme: theme, children: [
                  _ProfileRow(
                    icon: Icons.account_balance_outlined,
                    label: 'Contas para saque',
                    theme: theme,
                    onTap: () => context.push('/wallet/bank-accounts'),
                  ),
                  _ProfileRow(
                    icon: Icons.receipt_long_outlined,
                    label: 'Atividade da carteira',
                    theme: theme,
                    onTap: () => context.push('/wallet'),
                  ),
                ]),
                Padding(
                  padding: const EdgeInsets.only(top: 32),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('USUÁRIOS BLOQUEADOS',
                        style: TextStyle(color: colors.faint, fontWeight: FontWeight.bold, fontSize: 12, letterSpacing: 1)),
                    const SizedBox(height: 8),
                    if (_blocks == null)
                      const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: CircularProgressIndicator())
                    else if (_blocks!.isEmpty)
                      Text('Você não bloqueou ninguém.', style: TextStyle(color: colors.faint, fontSize: 13))
                    else
                      ..._blocks!.map((block) => Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            decoration: BoxDecoration(
                              color: colors.surface,
                              border: Border.all(color: colors.border),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Row(children: [
                              AppAvatar(initials: block.user?.initials ?? '?', theme: theme, size: 36),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(block.user?.name ?? 'Usuário',
                                    style: TextStyle(color: colors.ink, fontWeight: FontWeight.w600, fontSize: 14)),
                              ),
                              TextButton(onPressed: () => _confirmUnblock(block), child: const Text('Desbloquear')),
                            ]),
                          )),
                  ]),
                ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

class _SecuritySection extends StatelessWidget {
  final String title;
  final List<Widget> children;
  final AppTheme theme;
  const _SecuritySection({required this.title, required this.children, required this.theme});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title.toUpperCase(),
            style: TextStyle(color: colors.faint, fontWeight: FontWeight.bold, fontSize: 12, letterSpacing: 1)),
        const SizedBox(height: 8),
        ...List.generate(children.length * 2 - 1, (i) {
          if (i.isOdd) return Padding(padding: const EdgeInsets.only(left: 46), child: Divider(height: 1, color: colors.border));
          return children[i ~/ 2];
        }),
      ]),
    );
  }
}

class _StatusRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool ok;
  final AppTheme theme;
  final VoidCallback? onTap;
  const _StatusRow({required this.icon, required this.label, required this.ok, required this.theme, this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return InkWell(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 52),
        child: Row(children: [
          Icon(icon, size: 18, color: colors.muted),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: TextStyle(color: colors.ink, fontSize: 14))),
          Icon(ok ? Icons.check_circle : Icons.cancel_outlined, size: 16, color: ok ? colors.green : colors.faint),
          const SizedBox(width: 4),
          Text(ok ? 'Verificado' : 'Pendente', style: TextStyle(color: ok ? colors.green : colors.faint, fontWeight: FontWeight.w600, fontSize: 12)),
          if (onTap != null) ...[
            const SizedBox(width: 6),
            Icon(Icons.chevron_right, size: 16, color: colors.faint),
          ],
        ]),
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  final VoidCallback? onTap;
  final AppTheme theme;
  const _ProfileRow({required this.icon, required this.label, required this.theme, this.value, this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return InkWell(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 56),
        child: Row(children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(color: colors.alt, shape: BoxShape.circle),
            child: Icon(icon, size: 16, color: colors.muted),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: TextStyle(color: colors.ink, fontSize: 15))),
          if (value != null) Text(value!, style: TextStyle(color: colors.faint, fontSize: 13)),
          if (onTap != null) ...[
            const SizedBox(width: 6),
            Icon(Icons.chevron_right, size: 16, color: colors.faint),
          ],
        ]),
      ),
    );
  }
}
