import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/otp_input.dart';
import '../application/auth_controller.dart';

enum _Step { email, code, password, done }

/// Mirrors frontend/app/auth/forgot-password.tsx: email → 6-digit code →
/// new password → done. Same 30s resend cooldown, same dev_code surfacing
/// when SMTP isn't configured server-side (this environment's current state).
class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  static const _resendSeconds = 30;

  _Step _step = _Step.email;
  final _email = TextEditingController();
  final _code = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  bool _codeError = false;
  bool _loading = false;
  String? _devCode;
  int _remaining = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    for (final c in [_email, _code, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }

  void _restartCountdown() {
    _timer?.cancel();
    setState(() => _remaining = _resendSeconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_remaining <= 1) {
        t.cancel();
        setState(() => _remaining = 0);
      } else {
        setState(() => _remaining--);
      }
    });
  }

  Future<void> _sendCode() async {
    setState(() => _loading = true);
    try {
      final repo = ref.read(authRepositoryProvider);
      final result = await repo.forgotPassword(_email.text.trim().toLowerCase());
      setState(() {
        _devCode = result['dev_code'] as String?;
        _step = _Step.code;
      });
      _restartCountdown();
    } on ApiException catch (e) {
      _showError('Não foi possível enviar o código', e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _resetPassword() async {
    if (_password.text.length < 8) {
      _showError('Senha muito curta', 'Use pelo menos 8 caracteres.');
      return;
    }
    if (_password.text != _confirm.text) {
      _showError('As senhas não coincidem', 'Confira e tente de novo.');
      return;
    }
    setState(() => _loading = true);
    try {
      final repo = ref.read(authRepositoryProvider);
      await repo.resetPassword(
        email: _email.text.trim().toLowerCase(),
        code: _code.text,
        password: _password.text,
      );
      setState(() => _step = _Step.done);
    } on ApiException catch (e) {
      setState(() {
        _codeError = true;
        _step = _Step.code;
      });
      _showError('Não foi possível trocar a senha', e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
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

  void _back() {
    switch (_step) {
      case _Step.email:
        context.pop();
      case _Step.code:
        setState(() => _step = _Step.email);
      case _Step.password:
        setState(() => _step = _Step.code);
      case _Step.done:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              if (_step != _Step.done)
                Align(
                  alignment: Alignment.centerLeft,
                  child: IconButton(onPressed: _back, icon: Icon(Icons.arrow_back, color: colors.ink)),
                ),
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: _buildStep(theme),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStep(AppTheme theme) {
    final colors = theme.colors;
    switch (_step) {
      case _Step.email:
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Esqueceu sua senha?', style: theme.type.h1),
          const SizedBox(height: 8),
          Text(
            'Informe o e-mail da sua conta e enviaremos um código de recuperação.',
            style: theme.type.body.copyWith(color: colors.muted),
          ),
          const SizedBox(height: 16),
          AppTextField(
            controller: _email,
            theme: theme,
            label: 'E-mail',
            placeholder: 'voce@email.com',
            keyboardType: TextInputType.emailAddress,
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          AppButton(
            title: _loading ? 'Enviando...' : 'Enviar código',
            theme: theme,
            loading: _loading,
            onPressed: _email.text.trim().isNotEmpty && !_loading ? _sendCode : null,
          ),
        ]);

      case _Step.code:
        return Column(mainAxisSize: MainAxisSize.min, children: [
          Text('Confirme o código', style: theme.type.h1, textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Text(
            'Enviamos um código de 6 dígitos para\n${_email.text}',
            style: theme.type.body.copyWith(color: colors.muted),
            textAlign: TextAlign.center,
          ),
          if (_devCode != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(color: colors.accentSoft, borderRadius: BorderRadius.circular(12)),
              child: RichText(
                text: TextSpan(
                  style: theme.type.small.copyWith(color: colors.ink),
                  children: [
                    const TextSpan(text: 'Modo de desenvolvimento — código: '),
                    TextSpan(text: _devCode, style: const TextStyle(fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 20),
          OtpInput(
            controller: _code,
            theme: theme,
            error: _codeError,
            onChanged: (_) => setState(() => _codeError = false),
            onComplete: (_) => setState(() => _step = _Step.password),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: _remaining > 0 ? null : _sendCode,
            child: Text(
              _remaining > 0 ? 'Reenviar em ${_remaining}s' : 'Reenviar código',
              style: theme.type.small.copyWith(color: _remaining > 0 ? colors.faint : colors.primary),
            ),
          ),
        ]);

      case _Step.password:
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Crie uma nova senha', style: theme.type.h1),
          const SizedBox(height: 8),
          Text('Use pelo menos 8 caracteres.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          AppTextField(
            controller: _password,
            theme: theme,
            label: 'Nova senha',
            placeholder: '••••••••',
            obscureText: true,
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          AppTextField(
            controller: _confirm,
            theme: theme,
            label: 'Confirmar senha',
            placeholder: '••••••••',
            obscureText: true,
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          AppButton(
            title: _loading ? 'Salvando...' : 'Salvar nova senha',
            theme: theme,
            loading: _loading,
            onPressed: _password.text.isNotEmpty && _confirm.text.isNotEmpty && !_loading ? _resetPassword : null,
          ),
        ]);

      case _Step.done:
        return Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(color: colors.greenSoft, shape: BoxShape.circle),
            child: Icon(Icons.check, size: 36, color: colors.green),
          ),
          const SizedBox(height: 16),
          Text('Senha alterada.', style: theme.type.h1, textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Text('Agora é só entrar com sua nova senha.',
              style: theme.type.body.copyWith(color: colors.muted), textAlign: TextAlign.center),
          const SizedBox(height: 20),
          AppButton(title: 'Entrar', theme: theme, onPressed: () => context.go('/auth/login')),
        ]);
    }
  }
}
