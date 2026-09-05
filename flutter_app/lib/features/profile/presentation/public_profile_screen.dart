import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/review.dart';
import '../../../core/models/user.dart';
import '../../../core/models/user_stats.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/widgets/app_avatar.dart';
import '../../../core/widgets/empty_state.dart';

/// Mirrors frontend/app/user/[id].tsx: identity header, stat row, real
/// reputation block (completion/cancellation/repeat-client rates, avg
/// response time — from GET /users/{id}/stats, nothing fabricated), and
/// reviews list.
class PublicProfileScreen extends ConsumerStatefulWidget {
  final String userId;
  const PublicProfileScreen({super.key, required this.userId});

  @override
  ConsumerState<PublicProfileScreen> createState() => _PublicProfileScreenState();
}

class _PublicProfileScreenState extends ConsumerState<PublicProfileScreen> {
  AppUser? _profile;
  UserStats? _stats;
  List<Review> _reviews = [];
  bool _loading = true;
  bool _notFound = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(profileRepositoryProvider);
      final profile = await repo.fetchUser(widget.userId);
      final results = await Future.wait([repo.fetchStats(widget.userId), repo.fetchReviews(widget.userId)]);
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _stats = results[0] as UserStats;
        _reviews = results[1] as List<Review>;
      });
    } on ApiException {
      if (mounted) setState(() => _notFound = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;
    final bootstrap = ref.watch(bootstrapProvider).valueOrNull;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(children: [
              IconButton(onPressed: () => context.pop(), icon: Icon(Icons.arrow_back, color: colors.ink)),
              const SizedBox(width: 6),
              Text('Perfil', style: theme.type.h2.copyWith(fontSize: 18)),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _notFound || _profile == null
                    ? Center(
                        child: EmptyState(
                          icon: Icons.person_outline,
                          title: 'Perfil não encontrado',
                          body: 'Esse usuário pode ter sido removido.',
                          actionTitle: 'Voltar',
                          onAction: () => context.pop(),
                          theme: theme,
                        ),
                      )
                    : _buildBody(theme, bootstrap),
          ),
        ]),
      ),
    );
  }

  Widget _buildBody(dynamic theme, dynamic bootstrap) {
    final colors = theme.colors;
    final profile = _profile!;
    final stats = _stats;
    final hood = (bootstrap?.neighborhoods as List? ?? []).where((n) => n.id == profile.neighborhoodId).firstOrNull;
    final city = (bootstrap?.cities as List? ?? []).where((c) => c.id == profile.cityId).firstOrNull;
    final memberSince = profile.memberSince != null ? DateTime.tryParse(profile.memberSince!)?.year : null;

    final statRows = <(IconData, String, String)>[
      if (stats?.completionRate != null)
        (Icons.done_all, 'Taxa de conclusão', '${(stats!.completionRate! * 100).round()}%'),
      if (stats?.cancellationRateAsWorker != null)
        (Icons.cancel_outlined, 'Cancelamentos como fazedor', '${(stats!.cancellationRateAsWorker! * 100).round()}%'),
      if (stats?.cancellationRateAsClient != null)
        (Icons.cancel_outlined, 'Cancelamentos como cliente', '${(stats!.cancellationRateAsClient! * 100).round()}%'),
      if (stats?.repeatClientRate != null)
        (Icons.repeat, 'Clientes que voltaram', '${(stats!.repeatClientRate! * 100).round()}%'),
      if (stats?.avgResponseHours != null)
        (Icons.bolt_outlined, 'Tempo médio de resposta', '${stats!.avgResponseHours}h'),
    ];

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Center(
          child: Column(children: [
            AppAvatar(initials: profile.initials, theme: theme, size: 92),
            const SizedBox(height: 12),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Text(profile.name, style: theme.type.h1.copyWith(fontSize: 22)),
              if (profile.verifiedIdentity) ...[
                const SizedBox(width: 6),
                Icon(Icons.check_circle, size: 18, color: colors.green),
              ],
            ]),
            const SizedBox(height: 5),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.star, size: 13, color: colors.amber),
              const SizedBox(width: 4),
              Text('${profile.rating} (${profile.ratingCount})', style: theme.type.small.copyWith(color: colors.muted)),
            ]),
            if (hood != null || city != null) ...[
              const SizedBox(height: 5),
              Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.location_on_outlined, size: 13, color: colors.faint),
                const SizedBox(width: 4),
                Text('${hood != null ? "${hood.name} · " : ""}${city?.name ?? ""}',
                    style: theme.type.small.copyWith(color: colors.muted)),
              ]),
            ],
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(color: colors.primarySoft, borderRadius: BorderRadius.circular(999)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.military_tech_outlined, size: 12, color: colors.primary),
                const SizedBox(width: 4),
                Text(profile.level, style: TextStyle(color: colors.primary, fontWeight: FontWeight.bold, fontSize: 12)),
              ]),
            ),
            if (profile.bio != null && profile.bio!.isNotEmpty) ...[
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(profile.bio!, style: theme.type.small.copyWith(color: colors.muted), textAlign: TextAlign.center),
              ),
            ],
          ]),
        ),
        const SizedBox(height: 24),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          _StatColumn(label: 'Avaliação', value: '${profile.rating}', theme: theme, showDivider: false),
          _StatColumn(label: 'Serviços', value: '${profile.jobsDone}', theme: theme),
          _StatColumn(label: 'Desde', value: memberSince?.toString() ?? '—', theme: theme),
        ]),
        Padding(
          padding: const EdgeInsets.only(top: 32),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('REPUTAÇÃO', style: TextStyle(color: colors.faint, fontWeight: FontWeight.bold, fontSize: 12, letterSpacing: 1)),
            const SizedBox(height: 8),
            if (statRows.isEmpty)
              EmptyState(icon: Icons.bar_chart_outlined, title: 'Ainda sem histórico', theme: theme)
            else
              ...List.generate(statRows.length * 2 - 1, (i) {
                if (i.isOdd) {
                  return Padding(padding: const EdgeInsets.only(left: 46), child: Divider(height: 1, color: colors.border));
                }
                final row = statRows[i ~/ 2];
                return Container(
                  constraints: const BoxConstraints(minHeight: 48),
                  child: Row(children: [
                    Icon(row.$1, size: 18, color: colors.muted),
                    const SizedBox(width: 12),
                    Expanded(child: Text(row.$2, style: TextStyle(color: colors.ink, fontSize: 14))),
                    Text(row.$3, style: TextStyle(color: colors.muted, fontSize: 13)),
                  ]),
                );
              }),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 32),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('AVALIAÇÕES', style: TextStyle(color: colors.faint, fontWeight: FontWeight.bold, fontSize: 12, letterSpacing: 1)),
            const SizedBox(height: 8),
            if (_reviews.isEmpty)
              EmptyState(icon: Icons.star_border, title: 'Nenhuma avaliação ainda.', theme: theme)
            else
              ..._reviews.map((review) => Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: colors.surface,
                      border: Border.all(color: colors.border),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        AppAvatar(initials: review.author?.initials ?? '?', theme: theme, size: 36),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(review.author?.name ?? 'Usuário',
                                style: TextStyle(color: colors.ink, fontWeight: FontWeight.bold, fontSize: 14)),
                            Row(children: List.generate(
                                5, (i) => Icon(i < review.stars ? Icons.star : Icons.star_border, size: 12, color: colors.amber))),
                          ]),
                        ),
                      ]),
                      if (review.comment != null && review.comment!.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(review.comment!, style: theme.type.small.copyWith(color: colors.muted)),
                      ],
                    ]),
                  )),
          ]),
        ),
      ],
    );
  }
}

class _StatColumn extends StatelessWidget {
  final String label;
  final String value;
  final dynamic theme;
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

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
