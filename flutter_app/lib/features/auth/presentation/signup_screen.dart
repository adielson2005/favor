import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/geo.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../application/auth_controller.dart';

/// Mirrors frontend/app/auth/signup.tsx's 6-step wizard exactly: nome → email
/// → telefone → senha → local → preferencia. Same field-level validation
/// rules per step (`canContinue` in the RN file), same cascading
/// state→city→neighborhood fetch, same password strength/requirement
/// indicators. Google signup shows the same "not configured" dialog as
/// LoginScreen, for the same reason (no real client ID in this environment).
class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key});

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

enum _Step { nome, email, telefone, senha, local, preferencia }

class _SignupScreenState extends ConsumerState<SignupScreen> {
  int _stepIndex = 0;
  static const _steps = _Step.values;

  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _confirmPassword = TextEditingController();
  final _hoodSearch = TextEditingController();

  List<StateRef> _states = [];
  List<City> _cities = [];
  List<Neighborhood> _neighborhoods = [];
  String? _stateId;
  String? _cityId;
  String? _hoodId;
  String? _preference;
  bool _acceptTerms = false;
  bool _submitting = false;
  bool _success = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadStates();
  }

  @override
  void dispose() {
    for (final c in [_firstName, _lastName, _email, _phone, _password, _confirmPassword, _hoodSearch]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadStates() async {
    try {
      final repo = ref.read(bootstrapRepositoryProvider);
      final states = await repo.fetchStates();
      if (!mounted) return;
      setState(() {
        _states = states;
        if (states.length == 1) _stateId = states.first.id;
      });
      if (_stateId != null) await _loadCities(_stateId!);
    } catch (_) {
      // Same "swallow, let the user retry by picking manually" behavior as
      // the RN screen's bare .catch(() => {}).
    }
  }

  Future<void> _loadCities(String stateId) async {
    try {
      final repo = ref.read(bootstrapRepositoryProvider);
      final cities = await repo.fetchCities(stateId: stateId);
      if (!mounted) return;
      setState(() {
        _cities = cities;
        if (cities.length == 1) _cityId = cities.first.id;
      });
      if (_cityId != null) await _loadNeighborhoods(_cityId!);
    } catch (_) {}
  }

  Future<void> _loadNeighborhoods(String cityId) async {
    try {
      final repo = ref.read(bootstrapRepositoryProvider);
      final hoods = await repo.fetchNeighborhoods(cityId: cityId);
      if (!mounted) return;
      setState(() => _neighborhoods = hoods);
    } catch (_) {}
  }

  static String _formatPhoneBR(String raw) {
    final digits = raw.replaceAll(RegExp(r'\D'), '');
    final d = digits.length > 11 ? digits.substring(0, 11) : digits;
    if (d.length <= 2) return d;
    if (d.length <= 7) return '(${d.substring(0, 2)}) ${d.substring(2)}';
    return '(${d.substring(0, 2)}) ${d.substring(2, 7)}-${d.substring(7)}';
  }

  static bool _isValidPhoneBR(String formatted) {
    final digits = formatted.replaceAll(RegExp(r'\D'), '');
    return digits.length == 10 || digits.length == 11;
  }

  // colorKey is one of 'danger' | 'amber' | 'green' — resolved against the
  // current theme's colors at the call site (avoids passing a function
  // around just to pick one of three fields).
  static ({String label, int score, String colorKey}) _passwordStrength(String pw) {
    var score = 0;
    if (pw.length >= 8) score++;
    if (RegExp(r'[a-z]').hasMatch(pw) && RegExp(r'[A-Z]').hasMatch(pw)) score++;
    if (RegExp(r'\d').hasMatch(pw)) score++;
    if (RegExp(r'[^A-Za-z0-9]').hasMatch(pw)) score++;
    if (score <= 1) return (label: 'Fraca', score: score, colorKey: 'danger');
    if (score <= 2) return (label: 'Média', score: score, colorKey: 'amber');
    return (label: 'Forte', score: score, colorKey: 'green');
  }

  static Color _strengthColor(dynamic colors, String key) => switch (key) {
        'danger' => colors.danger,
        'amber' => colors.amber,
        _ => colors.green,
      };

  _Step get _step => _steps[_stepIndex];

  bool get _canContinue => switch (_step) {
        _Step.nome => _firstName.text.trim().length >= 2,
        _Step.email => RegExp(r'\S+@\S+\.\S+').hasMatch(_email.text),
        _Step.telefone => _isValidPhoneBR(_phone.text),
        _Step.senha => _password.text.length >= 8 &&
            RegExp(r'[a-z]', caseSensitive: false).hasMatch(_password.text) &&
            RegExp(r'\d').hasMatch(_password.text) &&
            _password.text == _confirmPassword.text,
        _Step.local => _cityId != null,
        _Step.preferencia => _preference != null && _acceptTerms,
      };

  bool get _hasProgress =>
      _firstName.text.trim().isNotEmpty ||
      _lastName.text.trim().isNotEmpty ||
      _email.text.trim().isNotEmpty ||
      _phone.text.trim().isNotEmpty ||
      _password.text.isNotEmpty;

  void _back() {
    if (_stepIndex > 0) {
      setState(() => _stepIndex--);
      return;
    }
    if (_hasProgress) {
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Você ainda não terminou seu cadastro.'),
          content: const Text('Quer continuar depois?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Continuar cadastro')),
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                context.go('/auth/welcome');
              },
              child: const Text('Sair'),
            ),
          ],
        ),
      );
    } else {
      context.go('/auth/welcome');
    }
  }

  Future<void> _next() async {
    if (!_canContinue) return;
    if (_stepIndex < _steps.length - 1) {
      setState(() => _stepIndex++);
      return;
    }
    await _submit();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    final name = '${_firstName.text.trim()} ${_lastName.text.trim()}'.trim();
    try {
      await ref.read(authControllerProvider.notifier).register(
            name: name,
            email: _email.text.trim().toLowerCase(),
            phone: _phone.text.replaceAll(RegExp(r'\D'), ''),
            password: _password.text,
            cityId: _cityId!,
            neighborhoodId: _hoodId,
            preference: _preference!,
            acceptTerms: _acceptTerms,
          );
      if (!mounted) return;
      setState(() => _success = true);
      Future.delayed(const Duration(milliseconds: 1600), () {
        if (mounted) context.go('/');
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;

    if (_success) {
      return Scaffold(
        backgroundColor: colors.bg,
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 84,
                height: 84,
                decoration: BoxDecoration(color: colors.greenSoft, shape: BoxShape.circle),
                child: Icon(Icons.check, size: 42, color: colors.green),
              ),
              const SizedBox(height: 16),
              Text('Pronto, ${_firstName.text.trim()}.', style: theme.type.h1, textAlign: TextAlign.center),
              const SizedBox(height: 4),
              Text('Seu fazum está pronto.', style: theme.type.body.copyWith(color: colors.muted)),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  IconButton(
                    onPressed: _back,
                    icon: Icon(_stepIndex == 0 ? Icons.close : Icons.arrow_back, color: colors.ink),
                  ),
                  Expanded(
                    child: Text('Criar conta', style: theme.type.h2.copyWith(color: colors.ink)),
                  ),
                  Text('${_stepIndex + 1}/${_steps.length}', style: theme.type.small.copyWith(color: colors.faint)),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: (_stepIndex + 1) / _steps.length,
                  minHeight: 3,
                  backgroundColor: colors.alt,
                  color: colors.primary,
                ),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: _buildStepBody(theme),
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Text(_error!, style: theme.type.small.copyWith(color: colors.danger)),
              ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              decoration: BoxDecoration(border: Border(top: BorderSide(color: colors.border))),
              child: Row(
                children: [
                  Expanded(
                    child: AppButton(
                      title: _stepIndex == 0 ? 'Cancelar' : 'Voltar',
                      theme: theme,
                      variant: AppButtonVariant.ghost,
                      onPressed: _back,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: AppButton(
                      title: _submitting
                          ? 'Criando conta...'
                          : _stepIndex == _steps.length - 1
                              ? 'Criar conta'
                              : 'Continuar',
                      theme: theme,
                      loading: _submitting,
                      onPressed: _canContinue && !_submitting ? _next : null,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepBody(AppTheme theme) {
    final colors = theme.colors;
    switch (_step) {
      case _Step.nome:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Como podemos chamar você?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Leva menos de um minuto.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 20),
          AppTextField(controller: _firstName, theme: theme, label: 'Nome', placeholder: 'Seu nome', onChanged: (_) => setState(() {})),
          const SizedBox(height: 12),
          AppTextField(controller: _lastName, theme: theme, label: 'Sobrenome', placeholder: 'Seu sobrenome (opcional)', onChanged: (_) => setState(() {})),
        ]);

      case _Step.email:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Como podemos entrar em contato?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Usaremos seu e-mail para proteger sua conta e avisar sobre seus pedidos.',
              style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 20),
          AppTextField(
            controller: _email,
            theme: theme,
            label: 'E-mail',
            placeholder: 'voce@email.com',
            keyboardType: TextInputType.emailAddress,
            onChanged: (_) => setState(() {}),
          ),
        ]);

      case _Step.telefone:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Qual seu telefone?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Usamos para confirmar sua conta e proteger pagamentos.',
              style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 20),
          AppTextField(
            controller: _phone,
            theme: theme,
            label: 'Telefone',
            placeholder: '(94) 99999-9999',
            keyboardType: TextInputType.phone,
            onChanged: (v) {
              final formatted = _formatPhoneBR(v);
              _phone.value = TextEditingValue(
                text: formatted,
                selection: TextSelection.collapsed(offset: formatted.length),
              );
              setState(() {});
            },
          ),
        ]);

      case _Step.senha:
        final strength = _password.text.isEmpty ? null : _passwordStrength(_password.text);
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Crie uma senha segura.', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Só você vai saber ela.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 20),
          AppTextField(
            controller: _password,
            theme: theme,
            label: 'Senha',
            placeholder: 'Mínimo 8 caracteres',
            obscureText: true,
            onChanged: (_) => setState(() {}),
          ),
          if (strength != null) ...[
            const SizedBox(height: 8),
            Row(children: List.generate(4, (i) {
              final active = i < strength.score;
              return Expanded(
                child: Container(
                  height: 4,
                  margin: EdgeInsets.only(right: i < 3 ? 4 : 0),
                  decoration: BoxDecoration(
                    color: active ? _strengthColor(colors, strength.colorKey) : colors.alt,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              );
            })),
            const SizedBox(height: 4),
            Text(strength.label, style: theme.type.small.copyWith(color: _strengthColor(colors, strength.colorKey))),
          ],
          const SizedBox(height: 12),
          AppTextField(
            controller: _confirmPassword,
            theme: theme,
            label: 'Confirmar senha',
            placeholder: 'Repita a senha',
            obscureText: true,
            onChanged: (_) => setState(() {}),
            error: _confirmPassword.text.isNotEmpty && _confirmPassword.text != _password.text
                ? 'As senhas não coincidem.'
                : null,
          ),
          const SizedBox(height: 12),
          _Requirement(met: _password.text.length >= 8, label: '8 caracteres ou mais', theme: theme),
          _Requirement(met: RegExp(r'[a-z]', caseSensitive: false).hasMatch(_password.text), label: 'uma letra', theme: theme),
          _Requirement(met: RegExp(r'\d').hasMatch(_password.text), label: 'um número', theme: theme),
        ]);

      case _Step.local:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Onde você está?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Usamos isso para mostrar pedidos e trabalhos perto de você.',
              style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 20),
          if (_states.length > 1) ...[
            Text('ESTADO', style: theme.type.micro.copyWith(color: colors.muted)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: _states
                  .map((s) => _Chip(
                        label: s.uf,
                        active: _stateId == s.id,
                        theme: theme,
                        onTap: () {
                          setState(() {
                            _stateId = s.id;
                            _cityId = null;
                            _hoodId = null;
                          });
                          _loadCities(s.id);
                        },
                      ))
                  .toList(),
            ),
            const SizedBox(height: 16),
          ],
          if (_stateId != null && _cities.length > 1) ...[
            Text('CIDADE', style: theme.type.micro.copyWith(color: colors.muted)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: _cities
                  .map((c) => _Chip(
                        label: c.name,
                        active: _cityId == c.id,
                        theme: theme,
                        onTap: () {
                          setState(() {
                            _cityId = c.id;
                            _hoodId = null;
                          });
                          _loadNeighborhoods(c.id);
                        },
                      ))
                  .toList(),
            ),
            const SizedBox(height: 16),
          ],
          if (_cityId != null) ...[
            Text('BAIRRO', style: theme.type.micro.copyWith(color: colors.muted)),
            const SizedBox(height: 8),
            AppTextField(
              controller: _hoodSearch,
              theme: theme,
              placeholder: 'Buscar bairro (opcional)',
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _neighborhoods
                  .where((n) => n.name.toLowerCase().contains(_hoodSearch.text.toLowerCase()))
                  .map((n) => _Chip(
                        label: n.name,
                        active: _hoodId == n.id,
                        theme: theme,
                        onTap: () => setState(() => _hoodId = _hoodId == n.id ? null : n.id),
                      ))
                  .toList(),
            ),
          ],
        ]);

      case _Step.preferencia:
        const preferences = [
          (key: 'client', icon: Icons.front_hand_outlined, title: 'Preciso de ajuda', body: 'Quero publicar tarefas para outras pessoas fazerem.'),
          (key: 'worker', icon: Icons.work_outline, title: 'Quero fazer serviços', body: 'Quero encontrar trabalhos perto de mim.'),
          (key: 'both', icon: Icons.swap_horiz, title: 'Quero os dois', body: 'Vou pedir ajuda e também fazer trabalhos.'),
        ];
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('O que você quer fazer no fazum?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text(
            'Isso só personaliza sua primeira experiência — você pode fazer os dois a qualquer momento.',
            style: theme.type.body.copyWith(color: colors.muted),
          ),
          const SizedBox(height: 20),
          ...preferences.map((p) {
            final active = _preference == p.key;
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: InkWell(
                onTap: () => setState(() => _preference = p.key),
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: active ? colors.primary : colors.border, width: active ? 2 : 1.5),
                    color: active ? colors.primarySoft : colors.surface,
                  ),
                  child: Row(children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: active ? colors.primary : colors.alt,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Icon(p.icon, size: 21, color: active ? colors.onPrimary : colors.muted),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(p.title, style: theme.type.bodyStrong),
                        const SizedBox(height: 2),
                        Text(p.body, style: theme.type.small.copyWith(color: colors.muted)),
                      ]),
                    ),
                    if (active) Icon(Icons.check_circle, color: colors.primary, size: 22),
                  ]),
                ),
              ),
            );
          }),
          const SizedBox(height: 8),
          InkWell(
            onTap: () => setState(() => _acceptTerms = !_acceptTerms),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                width: 22,
                height: 22,
                margin: const EdgeInsets.only(top: 1, right: 8),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: _acceptTerms ? colors.primary : colors.border, width: 1.5),
                  color: _acceptTerms ? colors.primary : Colors.transparent,
                ),
                child: _acceptTerms ? Icon(Icons.check, size: 14, color: colors.onPrimary) : null,
              ),
              Expanded(
                child: Text(
                  'Li e aceito os Termos de Uso e a Política de Privacidade do fazum.',
                  style: theme.type.small.copyWith(color: colors.muted),
                ),
              ),
            ]),
          ),
        ]);
    }
  }
}

class _Requirement extends StatelessWidget {
  final bool met;
  final String label;
  final AppTheme theme;
  const _Requirement({required this.met, required this.label, required this.theme});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(children: [
        Icon(met ? Icons.check_circle : Icons.circle_outlined, size: 14, color: met ? colors.green : colors.faint),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(fontSize: 12, color: met ? colors.ink : colors.faint)),
      ]),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool active;
  final AppTheme theme;
  final VoidCallback onTap;
  const _Chip({required this.label, required this.active, required this.theme, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: 36,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: active ? colors.primary : colors.surface,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: active ? colors.primary : colors.border),
        ),
        child: Text(label, style: theme.type.small.copyWith(color: active ? colors.onPrimary : colors.ink)),
      ),
    );
  }
}
