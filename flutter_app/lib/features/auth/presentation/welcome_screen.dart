import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_button.dart';

/// Mirrors frontend/app/auth/welcome.tsx — brand, one-line pitch, Entrar /
/// Criar conta, legal footer.
class WelcomeScreen extends ConsumerWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('fazum', style: theme.type.display.copyWith(color: colors.primary)),
                      const SizedBox(height: 16),
                      RichText(
                        textAlign: TextAlign.center,
                        text: TextSpan(
                          style: theme.type.body.copyWith(color: colors.muted),
                          children: [
                            const TextSpan(text: 'Precisou? '),
                            TextSpan(
                              text: 'FAZUM',
                              style: theme.type.body.copyWith(color: colors.primary, fontWeight: FontWeight.bold),
                            ),
                            const TextSpan(text: ' pedido.'),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  AppButton(title: 'Entrar', theme: theme, onPressed: () => context.push('/auth/login')),
                  const SizedBox(height: 12),
                  AppButton(
                    title: 'Criar conta',
                    theme: theme,
                    variant: AppButtonVariant.secondary,
                    onPressed: () => context.push('/auth/signup'),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              Text(
                'Ao continuar, você concorda com os Termos de Uso e a Política de Privacidade.',
                textAlign: TextAlign.center,
                style: theme.type.micro.copyWith(color: colors.faint),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}
