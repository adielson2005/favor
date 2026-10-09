import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/services/google_auth_service.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../application/auth_controller.dart';

/// Mirrors frontend/app/auth/login.tsx: identifier (email or phone) + senha,
/// "esqueci minha senha", link to signup, and a demo-accounts helper for
/// quick manual testing during development. Google login triggers the real
/// google_sign_in flow (GoogleAuthService) and only falls back to a
/// "not configured" message if GOOGLE_SERVER_CLIENT_ID wasn't passed at
/// build time — see google_auth_service.dart.
///
/// The demo-accounts helper (below) is gated behind kDebugMode so a
/// `flutter build apk --release` — what actually gets installed on a real
/// device or shared with testers — never ships the demo emails/password as
/// extractable strings, and never gives anyone who gets the APK a working
/// login shortcut. `flutter run` in debug mode keeps it for the dev team.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _identifier = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  bool _showDemo = false;
  String? _error;

  static const _demoAccounts = [
    ('Cliente', 'marina@fazum.demo'),
    ('Fazedor', 'joao@fazum.demo'),
    ('Admin', 'admin@fazum.demo'),
  ];
  static const _demoPassword = 'faze2024';

  @override
  void dispose() {
    _identifier.dispose();
    _password.dispose();
    super.dispose();
  }

  bool get _canSubmit => _identifier.text.trim().isNotEmpty && _password.text.isNotEmpty && !_loading;

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).login(
            identifier: _identifier.text,
            password: _password.text,
          );
      if (mounted) context.go('/');
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pressGoogle() async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final google = await GoogleAuthService.instance.signIn();
      await ref.read(authControllerProvider.notifier).loginWithGoogle(
            idToken: google.idToken,
            nonce: google.nonce,
          );
      if (mounted) context.go('/');
    } on GoogleAuthException catch (e) {
      if (!e.cancelled && mounted) setState(() => _error = e.message);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
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
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 12),
              IconButton(
                onPressed: () => context.canPop() ? context.pop() : context.go('/auth/welcome'),
                icon: Icon(Icons.arrow_back, color: colors.ink),
                alignment: Alignment.centerLeft,
              ),
              const SizedBox(height: 8),
              Text('fazum', style: theme.type.h1.copyWith(color: colors.primary)),
              const SizedBox(height: 24),
              Text('Precisou? Alguém faz.', style: theme.type.display),
              const SizedBox(height: 8),
              Text(
                'Entre para pedir ajuda ou encontrar trabalhos em Parauapebas.',
                style: theme.type.body.copyWith(color: colors.muted),
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: colors.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: colors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    AppTextField(
                      controller: _identifier,
                      theme: theme,
                      label: 'E-mail ou telefone',
                      placeholder: 'voce@email.com ou (94) 99999-9999',
                      keyboardType: TextInputType.emailAddress,
                      onChanged: (_) => setState(() {}),
                    ),
                    const SizedBox(height: 12),
                    AppTextField(
                      controller: _password,
                      theme: theme,
                      label: 'Senha',
                      placeholder: '••••••••',
                      obscureText: true,
                      onChanged: (_) => setState(() {}),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 8),
                      Text(_error!, style: theme.type.small.copyWith(color: colors.danger)),
                    ],
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => context.push('/auth/forgot-password'),
                        child: Text(
                          'Esqueci minha senha',
                          style: theme.type.small.copyWith(color: colors.primary),
                        ),
                      ),
                    ),
                    AppButton(
                      title: _loading ? 'Entrando...' : 'Entrar',
                      theme: theme,
                      loading: _loading,
                      onPressed: _canSubmit ? _submit : null,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: Divider(color: colors.border)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text('ou continue com', style: theme.type.micro.copyWith(color: colors.faint)),
                ),
                Expanded(child: Divider(color: colors.border)),
              ]),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _pressGoogle,
                icon: Icon(Icons.g_mobiledata, color: colors.ink),
                label: Text('Continuar com Google', style: theme.type.bodyStrong.copyWith(color: colors.ink)),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                  side: BorderSide(color: colors.border, width: 1.5),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: TextButton(
                  onPressed: () => context.push('/auth/signup'),
                  child: RichText(
                    text: TextSpan(
                      style: theme.type.small.copyWith(color: colors.muted),
                      children: [
                        const TextSpan(text: 'Ainda não tem conta? '),
                        TextSpan(
                          text: 'Criar conta',
                          style: theme.type.small.copyWith(color: colors.primary, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              if (kDebugMode) ...[
                const SizedBox(height: 8),
                Center(
                  child: TextButton(
                    onPressed: () => setState(() => _showDemo = !_showDemo),
                    child: Text(
                      _showDemo ? 'Ocultar contas demo' : 'Ver contas demo',
                      style: theme.type.small.copyWith(color: colors.faint),
                    ),
                  ),
                ),
                if (_showDemo)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: colors.alt, borderRadius: BorderRadius.circular(16)),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Preenche o formulário, senha $_demoPassword',
                            style: theme.type.micro.copyWith(color: colors.faint)),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          children: _demoAccounts.map((acc) {
                            return OutlinedButton(
                              onPressed: () => setState(() {
                                _identifier.text = acc.$2;
                                _password.text = _demoPassword;
                              }),
                              style: OutlinedButton.styleFrom(
                                side: BorderSide(color: colors.border),
                                backgroundColor: colors.surface,
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
                              ),
                              child: Text(acc.$1, style: theme.type.small.copyWith(color: colors.ink)),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
              ],
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
