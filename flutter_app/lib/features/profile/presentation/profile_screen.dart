import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../auth/application/auth_controller.dart';

/// Mirrors frontend/app/(tabs)/profile.tsx: header (avatar, name, rating,
/// location, level/mode badges, bio), stat row, and grouped action rows
/// (editar perfil, localização, alterar senha, carteira, atividade). Avatar
/// upload is plain image_picker → base64 here, without the RN app's custom
/// AvatarCropModal — that's a real, deliberate scope reduction (a crop UI is
/// a meaningfully bigger addition), not an oversight.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  bool _uploadingPhoto = false;

  Future<void> _refreshMe() => ref.read(authControllerProvider.notifier).refreshUser();

  Future<void> _pickAvatar() async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: ImageSource.gallery, imageQuality: 60);
      if (picked == null) return;
      setState(() => _uploadingPhoto = true);
      final bytes = await picked.readAsBytes();
      final me = ref.read(authControllerProvider).user!;
      await ref.read(profileRepositoryProvider).updateProfile(
            me.id,
            avatarB64: 'data:image/jpeg;base64,${base64Encode(bytes)}',
          );
      await _refreshMe();
    } on ApiException catch (e) {
      if (mounted) _showSnack('Não foi possível atualizar a foto: ${e.message}');
    } finally {
      if (mounted) setState(() => _uploadingPhoto = false);
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  void _openEditProfile() {
    final me = ref.read(authControllerProvider).user!;
    final name = TextEditingController(text: me.name);
    final bio = TextEditingController(text: me.bio ?? '');
    var saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Editar perfil', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              AppTextField(controller: name, theme: theme, label: 'Nome', onChanged: (_) => setSheetState(() {})),
              const SizedBox(height: 10),
              AppTextField(controller: bio, theme: theme, label: 'Descrição', onChanged: (_) => setSheetState(() {})),
              const SizedBox(height: 16),
              AppButton(
                title: 'Salvar',
                theme: theme,
                loading: saving,
                onPressed: saving
                    ? null
                    : () async {
                        setSheetState(() => saving = true);
                        try {
                          await ref
                              .read(profileRepositoryProvider)
                              .updateProfile(me.id, name: name.text.trim(), bio: bio.text.trim());
                          await _refreshMe();
                          if (sheetContext.mounted) Navigator.pop(sheetContext);
                        } on ApiException catch (e) {
                          setSheetState(() => saving = false);
                          _showSnack(e.message);
                        }
                      },
              ),
            ]),
          );
        },
      ),
    );
  }

  void _openLocation() {
    final me = ref.read(authControllerProvider).user!;
    final bootstrap = ref.read(bootstrapProvider).valueOrNull;
    final cities = bootstrap?.cities ?? [];
    var selectedCityId = me.cityId;
    var selectedHoodId = me.neighborhoodId;
    var saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          final colors = theme.colors;
          final hoods = (bootstrap?.neighborhoods ?? []).where((n) => n.cityId == selectedCityId).toList();

          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const Text('Localização', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(height: 16),
                if (cities.length > 1) ...[
                  Text('CIDADE', style: theme.type.micro.copyWith(color: colors.muted)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: cities
                        .map((c) => _Chip(
                              label: c.name,
                              active: selectedCityId == c.id,
                              theme: theme,
                              onTap: () => setSheetState(() {
                                selectedCityId = c.id;
                                selectedHoodId = null;
                              }),
                            ))
                        .toList(),
                  ),
                  const SizedBox(height: 16),
                ],
                Text('BAIRRO', style: theme.type.micro.copyWith(color: colors.muted)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: hoods
                      .map((n) => _Chip(
                            label: n.name,
                            active: selectedHoodId == n.id,
                            theme: theme,
                            onTap: () => setSheetState(() => selectedHoodId = n.id),
                          ))
                      .toList(),
                ),
                const SizedBox(height: 16),
                AppButton(
                  title: 'Salvar',
                  theme: theme,
                  loading: saving,
                  onPressed: saving
                      ? null
                      : () async {
                          setSheetState(() => saving = true);
                          try {
                            await ref.read(profileRepositoryProvider).updateProfile(
                                  me.id,
                                  cityId: selectedCityId,
                                  neighborhoodId: selectedHoodId,
                                );
                            await _refreshMe();
                            if (sheetContext.mounted) Navigator.pop(sheetContext);
                          } on ApiException catch (e) {
                            setSheetState(() => saving = false);
                            _showSnack(e.message);
                          }
                        },
                ),
              ]),
            ),
          );
        },
      ),
    );
  }

  void _openChangePassword() {
    final me = ref.read(authControllerProvider).user!;
    final current = TextEditingController();
    final newPassword = TextEditingController();
    final confirm = TextEditingController();
    var saving = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          final theme = ref.read(themeProviderForScreens);
          final colors = theme.colors;
          final hasPassword = me.hasPassword ?? false;
          final canSave = (!hasPassword || current.text.isNotEmpty) &&
              newPassword.text.isNotEmpty &&
              confirm.text.isNotEmpty &&
              !saving;

          return Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 20,
            ),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(hasPassword ? 'Alterar senha' : 'Criar senha',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 8),
              if (!hasPassword)
                Text(
                  'Sua conta ainda não tem senha (você entra só com o Google). '
                  'Crie uma para também poder entrar com e-mail ou telefone.',
                  style: theme.type.small.copyWith(color: colors.muted),
                ),
              const SizedBox(height: 12),
              if (hasPassword) ...[
                AppTextField(
                  controller: current,
                  theme: theme,
                  label: 'Senha atual',
                  obscureText: true,
                  onChanged: (_) => setSheetState(() {}),
                ),
                const SizedBox(height: 10),
              ],
              AppTextField(
                controller: newPassword,
                theme: theme,
                label: 'Nova senha',
                placeholder: 'Mínimo 8 caracteres',
                obscureText: true,
                onChanged: (_) => setSheetState(() {}),
              ),
              const SizedBox(height: 10),
              AppTextField(
                controller: confirm,
                theme: theme,
                label: 'Confirmar nova senha',
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
                        if (newPassword.text.length < 8) {
                          _showSnack('Use pelo menos 8 caracteres.');
                          return;
                        }
                        if (newPassword.text != confirm.text) {
                          _showSnack('As senhas não coincidem.');
                          return;
                        }
                        setSheetState(() => saving = true);
                        try {
                          await ref.read(authRepositoryProvider).changePassword(
                                currentPassword: hasPassword ? current.text : null,
                                newPassword: newPassword.text,
                              );
                          if (sheetContext.mounted) Navigator.pop(sheetContext);
                          // The backend invalidates this session as a side effect of
                          // changing the password (token_version bump) — the cached
                          // token is already stale, so log out and send to welcome.
                          await ref.read(authControllerProvider.notifier).logout();
                          if (mounted) context.go('/auth/welcome');
                        } on ApiException catch (e) {
                          setSheetState(() => saving = false);
                          _showSnack(e.message);
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

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final me = ref.watch(authControllerProvider).user;
    final mode = ref.watch(modeControllerProvider);
    final bootstrap = ref.watch(bootstrapProvider).valueOrNull;

    if (me == null) return Scaffold(backgroundColor: colors.bg);

    final hood = (bootstrap?.neighborhoods ?? []).where((n) => n.id == me.neighborhoodId).firstOrNull;
    final city = (bootstrap?.cities ?? []).where((c) => c.id == me.cityId).firstOrNull;
    final memberSince = me.memberSince != null ? DateTime.tryParse(me.memberSince!)?.year : null;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: IconButton(onPressed: () => context.push('/settings'), icon: Icon(Icons.settings_outlined, color: colors.muted)),
            ),
            Center(
              child: Column(children: [
                GestureDetector(
                  onTap: _uploadingPhoto ? null : _pickAvatar,
                  child: Opacity(
                    opacity: _uploadingPhoto ? 0.5 : 1,
                    child: Stack(children: [
                      AppAvatar(initials: me.initials, theme: theme, size: 92),
                      Positioned(
                        right: -2,
                        bottom: -2,
                        child: Container(
                          width: 30,
                          height: 30,
                          decoration: BoxDecoration(
                            color: colors.primary,
                            shape: BoxShape.circle,
                            border: Border.all(color: colors.bg, width: 3),
                          ),
                          child: Icon(Icons.camera_alt, size: 14, color: colors.onPrimary),
                        ),
                      ),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Text(me.name, style: theme.type.h1.copyWith(fontSize: 22)),
                  if (me.verifiedIdentity) ...[
                    const SizedBox(width: 6),
                    Icon(Icons.check_circle, size: 18, color: colors.green),
                  ],
                ]),
                const SizedBox(height: 5),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.star, size: 13, color: colors.amber),
                  const SizedBox(width: 4),
                  Text('${me.rating} (${me.ratingCount})', style: theme.type.small.copyWith(color: colors.muted)),
                ]),
                const SizedBox(height: 5),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.location_on_outlined, size: 13, color: colors.faint),
                  const SizedBox(width: 4),
                  Text(
                    '${hood != null ? "${hood.name} · " : ""}${city?.name ?? "Parauapebas"}, PA',
                    style: theme.type.small.copyWith(color: colors.muted),
                  ),
                ]),
                const SizedBox(height: 12),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(color: colors.primarySoft, borderRadius: BorderRadius.circular(999)),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.military_tech_outlined, size: 12, color: colors.primary),
                      const SizedBox(width: 4),
                      Text(me.level, style: TextStyle(color: colors.primary, fontWeight: FontWeight.bold, fontSize: 12)),
                    ]),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(color: colors.alt, borderRadius: BorderRadius.circular(999)),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(mode == 'client' ? Icons.person_outline : Icons.handyman_outlined, size: 12, color: colors.muted),
                      const SizedBox(width: 4),
                      Text(mode == 'client' ? 'Cliente' : 'Fazedor',
                          style: TextStyle(color: colors.muted, fontWeight: FontWeight.w600, fontSize: 12)),
                    ]),
                  ),
                ]),
                if (me.bio != null && me.bio!.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text(me.bio!, style: theme.type.small.copyWith(color: colors.muted), textAlign: TextAlign.center),
                  ),
                ],
              ]),
            ),
            const SizedBox(height: 24),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              _StatColumn(label: 'Avaliação', value: '${me.rating}', theme: theme, showDivider: false),
              _StatColumn(label: 'Serviços', value: '${me.jobsDone}', theme: theme),
              _StatColumn(label: 'Desde', value: memberSince?.toString() ?? '2025', theme: theme),
            ]),
            _Section(title: 'Minha conta', theme: theme, children: [
              _ProfileRow(icon: Icons.person_outline, label: 'Editar perfil', theme: theme, onTap: _openEditProfile),
              _ProfileRow(
                icon: Icons.location_on_outlined,
                label: 'Localização',
                value: hood?.name ?? city?.name,
                theme: theme,
                onTap: _openLocation,
              ),
              _ProfileRow(icon: Icons.lock_outline, label: 'Alterar senha', theme: theme, onTap: _openChangePassword),
              _ProfileRow(
                icon: Icons.verified_user_outlined,
                label: 'Verificação',
                value: me.verifiedIdentity ? 'Identidade verificada' : 'Pendente',
                valueColor: me.verifiedIdentity ? colors.green : null,
                theme: theme,
              ),
              _ProfileRow(
                icon: Icons.shield_outlined,
                label: 'Segurança',
                theme: theme,
                onTap: () => context.push('/security'),
              ),
            ]),
            _Section(title: 'Financeiro', theme: theme, children: [
              _ProfileRow(
                icon: Icons.account_balance_wallet_outlined,
                label: 'fazumPay',
                value: 'Minha carteira',
                theme: theme,
                onTap: () => context.push('/wallet'),
              ),
            ]),
            _Section(title: 'Minha conta (sessão)', theme: theme, children: [
              _ProfileRow(
                icon: Icons.logout,
                label: 'Sair',
                theme: theme,
                danger: true,
                onTap: () => ref.read(authControllerProvider.notifier).logout(),
              ),
            ]),
          ],
        ),
      ),
    );
  }
}

class _StatColumn extends StatelessWidget {
  final String label;
  final String value;
  final AppTheme theme;
  final bool showDivider;
  const _StatColumn({required this.label, required this.value, required this.theme, this.showDivider = true});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: showDivider ? BoxDecoration(border: Border(left: BorderSide(color: colors.border))) : null,
      child: Column(children: [
        Text(value, style: theme.type.h1.copyWith(fontSize: 19)),
        const SizedBox(height: 2),
        Text(label, style: TextStyle(color: colors.faint, fontSize: 12)),
      ]),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  final AppTheme theme;
  const _Section({required this.title, required this.children, required this.theme});

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return Padding(
      padding: const EdgeInsets.only(top: 32),
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

class _ProfileRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  final Color? valueColor;
  final bool danger;
  final VoidCallback? onTap;
  final AppTheme theme;

  const _ProfileRow({
    required this.icon,
    required this.label,
    required this.theme,
    this.value,
    this.valueColor,
    this.danger = false,
    this.onTap,
  });

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
            decoration: BoxDecoration(color: danger ? colors.dangerSoft : colors.alt, shape: BoxShape.circle),
            child: Icon(icon, size: 16, color: danger ? colors.danger : colors.muted),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(label, style: TextStyle(color: danger ? colors.danger : colors.ink, fontSize: 15)),
          ),
          if (value != null)
            Text(value!, style: TextStyle(color: valueColor ?? colors.faint, fontSize: 13)),
          if (onTap != null) ...[
            const SizedBox(width: 6),
            Icon(Icons.chevron_right, size: 16, color: colors.faint),
          ],
        ]),
      ),
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
        child: Text(label, style: TextStyle(color: active ? colors.onPrimary : colors.ink, fontSize: 13)),
      ),
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
