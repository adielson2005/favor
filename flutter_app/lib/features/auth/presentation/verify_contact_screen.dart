import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/otp_input.dart';
import '../application/auth_controller.dart';

enum ContactChannel { email, phone }

/// Shared body for frontend/app/auth/verify-email.tsx and verify-phone.tsx —
/// same structure in both (auto-send on open, 6-digit code, 30s resend
/// cooldown, dev_code surfaced when SMTP/SMS aren't configured), differing
/// only in which repository calls/copy to use. Kept as one widget rather
/// than two near-duplicate files.
class VerifyContactScreen extends ConsumerStatefulWidget {
  final ContactChannel channel;
  const VerifyContactScreen({super.key, required this.channel});

  @override
  ConsumerState<VerifyContactScreen> createState() => _VerifyContactScreenState();
}

class _VerifyContactScreenState extends ConsumerState<VerifyContactScreen> {
  static const _resendSeconds = 30;

  final _code = TextEditingController();
  bool _error = false;
  bool _sending = false;
  bool _verifying = false;
  bool _done = false;
  String? _devCode;
  int _remaining = 0;
  Timer? _timer;

  bool get _isEmail => widget.channel == ContactChannel.email;

  @override
  void initState() {
    super.initState();
    _sendCode();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _code.dispose();
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
    setState(() => _sending = true);
    try {
      final repo = ref.read(authRepositoryProvider);
      final result = _isEmail ? await repo.sendVerification() : await repo.sendPhoneVerification();
      setState(() => _devCode = result['dev_code'] as String?);
      _restartCountdown();
    } on ApiException catch (e) {
      _showDialog('Não foi possível enviar o código', e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _verify(String code) async {
    setState(() => _verifying = true);
    try {
      final repo = ref.read(authRepositoryProvider);
      if (_isEmail) {
        await repo.verifyEmail(code);
      } else {
        await repo.verifyPhone(code);
      }
      await ref.read(authControllerProvider.notifier).refreshUser();
      setState(() => _done = true);
    } on ApiException catch (e) {
      setState(() => _error = true);
      _showDialog('Código incorreto', e.message);
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  void _showDialog(String title, String message) {
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
    final label = _isEmail ? 'e-mail' : 'telefone';

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: IconButton(
                  onPressed: () => context.canPop() ? context.pop() : context.go('/'),
                  icon: Icon(Icons.arrow_back, color: colors.ink),
                ),
              ),
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: _done
                        ? Column(mainAxisSize: MainAxisSize.min, children: [
                            Container(
                              width: 72,
                              height: 72,
                              decoration: BoxDecoration(color: colors.greenSoft, shape: BoxShape.circle),
                              child: Icon(Icons.check, size: 36, color: colors.green),
                            ),
                            const SizedBox(height: 16),
                            Text('${_isEmail ? "E-mail" : "Telefone"} verificado.',
                                style: theme.type.h1, textAlign: TextAlign.center),
                            const SizedBox(height: 20),
                            AppButton(
                              title: 'Continuar',
                              theme: theme,
                              onPressed: () => context.canPop() ? context.pop() : context.go('/'),
                            ),
                          ])
                        : Column(mainAxisSize: MainAxisSize.min, children: [
                            Text('Confira seu $label', style: theme.type.h1, textAlign: TextAlign.center),
                            const SizedBox(height: 8),
                            Text('Enviamos um código de 6 dígitos para o seu $label',
                                style: theme.type.body.copyWith(color: colors.muted), textAlign: TextAlign.center),
                            if (_devCode != null) ...[
                              const SizedBox(height: 16),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                decoration:
                                    BoxDecoration(color: colors.accentSoft, borderRadius: BorderRadius.circular(12)),
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
                              error: _error,
                              onChanged: (_) => setState(() => _error = false),
                              onComplete: _verify,
                            ),
                            if (_verifying) ...[
                              const SizedBox(height: 12),
                              Text('Verificando...', style: theme.type.small.copyWith(color: colors.muted)),
                            ],
                            const SizedBox(height: 16),
                            TextButton(
                              onPressed: _remaining > 0 || _sending ? null : _sendCode,
                              child: Text(
                                _remaining > 0 ? 'Reenviar em ${_remaining}s' : 'Reenviar código',
                                style: theme.type.small.copyWith(color: _remaining > 0 ? colors.faint : colors.primary),
                              ),
                            ),
                          ]),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
