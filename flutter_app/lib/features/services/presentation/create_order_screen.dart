import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/errors/api_exception.dart';
import '../../../core/models/geo.dart';
import '../../../core/providers.dart';
import '../../../core/theme/theme_controller.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../auth/application/auth_controller.dart';

/// Mirrors frontend/app/create.tsx's 7-step wizard (need → category →
/// details → photos → where → when → budget) for the CREATE path only —
/// edit/rehire prefill depend on richer order-detail state (an existing
/// order's full field set) than FASE 7's OrderDetailScreen exposes yet,
/// so this is scoped to publishing a brand-new necessidade,
/// same scope discipline as every other phase so far.
class CreateOrderScreen extends ConsumerStatefulWidget {
  const CreateOrderScreen({super.key});

  @override
  ConsumerState<CreateOrderScreen> createState() => _CreateOrderScreenState();
}

enum _Step { need, category, details, photos, where, when, budget }

// Same category-specific extra-field map as EXTRA_FIELDS in create.tsx.
const _extraFields = <String, List<(String key, String label, String placeholder)>>{
  'cat-entregas': [
    ('origem', 'De onde?', 'Ex: Correios do centro'),
    ('destino', 'Para onde?', 'Ex: Rua B, Cidade Nova'),
  ],
  'cat-compras': [('local_compra', 'Onde comprar?', 'Ex: Supermercado do bairro')],
  'cat-casa': [('ambiente', 'Qual ambiente ou item?', 'Ex: Guarda-roupa de 6 portas')],
  'cat-tecnologia': [('equipamento', 'Qual equipamento?', 'Ex: Notebook Dell')],
  'cat-veiculos': [('veiculo', 'Qual veículo?', 'Ex: Honda CG 160')],
  'cat-pets': [('pet', 'Sobre o pet', 'Ex: Golden retriever, dócil')],
  'cat-documentos': [('documento', 'Qual documento?', 'Ex: Envelope lacrado')],
  'cat-eventos': [('evento', 'Qual evento?', 'Ex: Aniversário no salão de festas')],
  'cat-profissionais': [('prazo', 'Prazo', 'Ex: Até sexta-feira')],
};

const _dates = ['Hoje', 'Amanhã', 'Esta semana', 'A combinar'];
const _recurrenceOptions = [
  ('none', 'Não se repete'),
  ('weekly', 'Semanal'),
  ('biweekly', 'Quinzenal'),
  ('monthly', 'Mensal'),
];
const _maxPhotos = 4;

class _CreateOrderScreenState extends ConsumerState<CreateOrderScreen> {
  int _stepIndex = 0;
  static const _steps = _Step.values;

  final _title = TextEditingController();
  final _description = TextEditingController();
  final _hoodSearch = TextEditingController();
  final _budget = TextEditingController();
  final _timeLabel = TextEditingController();
  final Map<String, TextEditingController> _extraControllers = {};

  String _type = 'favor';
  String? _categoryId;
  String? _subcategoryId;
  final Map<String, String> _fields = {};
  final List<String> _photos = [];
  String? _hoodId;
  String _dateLabel = 'Hoje';
  bool _urgent = false;
  String _recurrence = 'none';
  bool _publishing = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _hoodSearch.dispose();
    _budget.dispose();
    _timeLabel.dispose();
    for (final c in _extraControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  _Step get _step => _steps[_stepIndex];

  bool get _canContinue => switch (_step) {
        _Step.need => _title.text.trim().length >= 3,
        _Step.category => _categoryId != null,
        _Step.details => true,
        _Step.photos => true,
        _Step.where => _hoodId != null,
        _Step.when => _dateLabel.isNotEmpty,
        _Step.budget => (double.tryParse(_budget.text) ?? 0) > 0,
      };

  Future<void> _pickPhoto() async {
    if (_photos.length >= _maxPhotos) return;
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: ImageSource.gallery, imageQuality: 40);
      if (picked == null) return;
      final bytes = await picked.readAsBytes();
      final b64 = base64Encode(bytes);
      setState(() => _photos.add('data:image/jpeg;base64,$b64'));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Não foi possível acessar as fotos: $e')),
      );
    }
  }

  void _back() {
    if (_stepIndex > 0) {
      setState(() => _stepIndex--);
    } else if (context.canPop()) {
      context.pop();
    } else {
      context.go('/');
    }
  }

  Future<void> _next() async {
    if (!_canContinue) return;
    if (_stepIndex < _steps.length - 1) {
      setState(() => _stepIndex++);
      return;
    }
    await _publish();
  }

  Future<void> _publish() async {
    setState(() {
      _publishing = true;
      _error = null;
    });
    final me = ref.read(authControllerProvider).user;
    final bootstrap = ref.read(bootstrapProvider).valueOrNull;
    final cityId = bootstrap?.cities.where((c) => c.id == me?.cityId).firstOrNull?.id ??
        bootstrap?.cities.firstOrNull?.id ??
        'city-parauapebas';
    try {
      final repo = ref.read(ordersRepositoryProvider);
      final created = await repo.createOrder(
        title: _title.text.trim(),
        description: _description.text.trim(),
        type: _type,
        categoryId: _categoryId!,
        subcategoryId: _subcategoryId,
        cityId: cityId,
        neighborhoodId: _hoodId,
        dateLabel: _dateLabel,
        timeLabel: _timeLabel.text.trim(),
        budget: double.parse(_budget.text),
        photos: _photos,
        fields: _fields,
        urgent: _urgent,
        recurrence: _recurrence,
      );
      if (!mounted) return;
      context.pushReplacement('/order/${created.id}');
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = ref.watch(themeProviderForScreens);
    final colors = theme.colors;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(children: [
                IconButton(
                  onPressed: _back,
                  icon: Icon(_stepIndex == 0 ? Icons.close : Icons.arrow_back, color: colors.ink),
                ),
                Expanded(child: Text('Novo pedido', style: theme.type.h2.copyWith(fontSize: 16))),
                Text('${_stepIndex + 1}/${_steps.length}', style: theme.type.small.copyWith(color: colors.faint)),
              ]),
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
              child: Row(children: [
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
                    title: _stepIndex == _steps.length - 1 ? 'Publicar pedido' : 'Continuar',
                    theme: theme,
                    loading: _publishing,
                    onPressed: _canContinue && !_publishing ? _next : null,
                  ),
                ),
              ]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepBody(AppTheme theme) {
    final colors = theme.colors;
    final bootstrap = ref.watch(bootstrapProvider).valueOrNull;
    final categories = bootstrap?.categories ?? <Category>[];
    final neighborhoods = bootstrap?.neighborhoods ?? [];
    final category = categories.where((c) => c.id == _categoryId).firstOrNull;
    final extras = _categoryId != null ? (_extraFields[_categoryId] ?? const []) : const [];

    switch (_step) {
      case _Step.need:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('O que você precisa?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Descreva em poucas palavras.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          AppTextField(controller: _title, theme: theme, placeholder: 'Ex: Buscar uma encomenda', onChanged: (_) => setState(() {})),
          const SizedBox(height: 24),
          _TypeOption(
            title: 'Favor',
            body: 'Tarefa simples e pontual',
            icon: Icons.front_hand_outlined,
            active: _type == 'favor',
            theme: theme,
            onTap: () => setState(() => _type = 'favor'),
          ),
          const SizedBox(height: 10),
          _TypeOption(
            title: 'Serviço',
            body: 'Exige mais tempo ou habilidade',
            icon: Icons.build_outlined,
            active: _type == 'servico',
            theme: theme,
            onTap: () => setState(() => _type = 'servico'),
          ),
        ]);

      case _Step.category:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Qual categoria combina?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Isso ajuda os fazedores certos a encontrarem seu pedido.',
              style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: categories.map((cat) {
              final active = _categoryId == cat.id;
              return SizedBox(
                width: (MediaQuery.of(context).size.width - 40 - 10) / 2,
                child: InkWell(
                  onTap: () => setState(() {
                    _categoryId = cat.id;
                    _subcategoryId = null;
                  }),
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: colors.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: active ? colors.primary : colors.border, width: 1.5),
                    ),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Icon(Icons.auto_awesome, size: 20, color: active ? colors.primary : colors.muted),
                      const SizedBox(height: 8),
                      Text(cat.name, style: TextStyle(color: colors.ink, fontSize: 13, fontWeight: FontWeight.bold)),
                    ]),
                  ),
                ),
              );
            }).toList(),
          ),
          if (category != null && category.subcategories.isNotEmpty) ...[
            const SizedBox(height: 24),
            Text('MAIS ESPECÍFICO (OPCIONAL)', style: theme.type.micro.copyWith(color: colors.muted)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: category.subcategories.map((sub) {
                final active = _subcategoryId == sub.id;
                return InkWell(
                  onTap: () => setState(() => _subcategoryId = active ? null : sub.id),
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
                    child: Text(sub.name, style: TextStyle(color: active ? colors.onPrimary : colors.ink, fontSize: 13)),
                  ),
                );
              }).toList(),
            ),
          ],
        ]);

      case _Step.details:
        for (final extra in extras) {
          _extraControllers.putIfAbsent(extra.$1, () => TextEditingController(text: _fields[extra.$1]));
        }
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Conte um pouco mais.', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Detalhes ajudam a receber propostas melhores.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          TextField(
            controller: _description,
            maxLines: 5,
            style: theme.type.body,
            decoration: InputDecoration(
              hintText: 'Descreva a tarefa...',
              filled: true,
              fillColor: colors.surface,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: colors.border)),
            ),
          ),
          ...extras.map((extra) => Padding(
                padding: const EdgeInsets.only(top: 12),
                child: AppTextField(
                  controller: _extraControllers[extra.$1]!,
                  theme: theme,
                  label: extra.$2,
                  placeholder: extra.$3,
                  onChanged: (v) => _fields[extra.$1] = v,
                ),
              )),
        ]);

      case _Step.photos:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Quer adicionar fotos?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Opcional — ajuda a explicar o que você precisa.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          Wrap(spacing: 10, runSpacing: 10, children: [
            ..._photos.asMap().entries.map((entry) {
              return Stack(clipBehavior: Clip.none, children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: Image.memory(
                    base64Decode(entry.value.split(',').last),
                    width: 84,
                    height: 84,
                    fit: BoxFit.cover,
                  ),
                ),
                Positioned(
                  top: -6,
                  right: -6,
                  child: GestureDetector(
                    onTap: () => setState(() => _photos.removeAt(entry.key)),
                    child: Container(
                      width: 22,
                      height: 22,
                      decoration: BoxDecoration(color: colors.danger, shape: BoxShape.circle),
                      child: const Icon(Icons.close, size: 13, color: Colors.white),
                    ),
                  ),
                ),
              ]);
            }),
            if (_photos.length < _maxPhotos)
              InkWell(
                onTap: _pickPhoto,
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: colors.border, width: 1.5),
                    color: colors.surface,
                  ),
                  child: Icon(Icons.camera_alt_outlined, size: 22, color: colors.muted),
                ),
              ),
          ]),
        ]);

      case _Step.where:
        final filtered = neighborhoods
            .where((n) => n.name.toLowerCase().contains(_hoodSearch.text.toLowerCase()))
            .toList();
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Onde será?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Parauapebas, PA · escolha o bairro', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          AppTextField(controller: _hoodSearch, theme: theme, placeholder: 'Buscar bairro...', onChanged: (_) => setState(() {})),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: filtered.map((n) {
              final active = _hoodId == n.id;
              return InkWell(
                onTap: () => setState(() => _hoodId = n.id),
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
                  child: Text(n.name, style: TextStyle(color: active ? colors.onPrimary : colors.ink, fontSize: 13)),
                ),
              );
            }).toList(),
          ),
        ]);

      case _Step.when:
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Quando?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Escolha o melhor momento.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            children: _dates.map((d) {
              final active = _dateLabel == d;
              return InkWell(
                onTap: () => setState(() => _dateLabel = d),
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
                  child: Text(d, style: TextStyle(color: active ? colors.onPrimary : colors.ink, fontSize: 13)),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 20),
          AppTextField(controller: _timeLabel, theme: theme, label: 'Horário (opcional)', placeholder: 'Ex: até 17:00'),
          const SizedBox(height: 24),
          InkWell(
            onTap: () => setState(() => _urgent = !_urgent),
            borderRadius: BorderRadius.circular(16),
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: _urgent ? colors.danger : colors.border, width: 1.5),
                color: _urgent ? colors.dangerSoft : colors.surface,
              ),
              child: Row(children: [
                Icon(_urgent ? Icons.bolt : Icons.bolt_outlined, size: 20, color: _urgent ? colors.danger : colors.muted),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Preciso agora', style: TextStyle(color: colors.ink, fontWeight: FontWeight.bold, fontSize: 14)),
                    Text('Destaca seu pedido para quem está por perto.', style: TextStyle(color: colors.muted, fontSize: 12)),
                  ]),
                ),
                Icon(_urgent ? Icons.check_circle : Icons.circle_outlined, size: 22, color: _urgent ? colors.danger : colors.faint),
              ]),
            ),
          ),
          const SizedBox(height: 24),
          Text('Se repete?', style: theme.type.h2.copyWith(fontSize: 15)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: _recurrenceOptions.map((r) {
              final active = _recurrence == r.$1;
              return InkWell(
                onTap: () => setState(() => _recurrence = r.$1),
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
                  child: Text(r.$2, style: TextStyle(color: active ? colors.onPrimary : colors.ink, fontSize: 13)),
                ),
              );
            }).toList(),
          ),
        ]);

      case _Step.budget:
        final selectedHood = neighborhoods.where((n) => n.id == _hoodId).firstOrNull;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Quanto pretende pagar?', style: theme.type.h1),
          const SizedBox(height: 6),
          Text('Você ainda pode negociar nas propostas.', style: theme.type.body.copyWith(color: colors.muted)),
          const SizedBox(height: 16),
          Row(children: [
            Text('R\$', style: TextStyle(color: colors.muted, fontSize: 26, fontWeight: FontWeight.bold)),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _budget,
                keyboardType: TextInputType.number,
                onChanged: (_) => setState(() {}),
                style: TextStyle(fontSize: 44, fontWeight: FontWeight.w800, color: colors.ink),
                decoration: const InputDecoration(border: InputBorder.none, hintText: '0'),
              ),
            ),
          ]),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: colors.surface,
              border: Border.all(color: colors.border),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_title.text.isEmpty ? 'Seu pedido' : _title.text,
                  style: TextStyle(color: colors.ink, fontSize: 15, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text(
                '${category?.name ?? ""}${_type == "favor" ? " · Favor" : " · Serviço"}',
                style: TextStyle(color: colors.muted, fontSize: 13),
              ),
              const SizedBox(height: 6),
              Text(
                '${selectedHood?.name ?? ""} · $_dateLabel${_timeLabel.text.isNotEmpty ? " · ${_timeLabel.text}" : ""}',
                style: TextStyle(color: colors.muted, fontSize: 13),
              ),
            ]),
          ),
        ]);
    }
  }
}

class _TypeOption extends StatelessWidget {
  final String title;
  final String body;
  final IconData icon;
  final bool active;
  final AppTheme theme;
  final VoidCallback onTap;

  const _TypeOption({
    required this.title,
    required this.body,
    required this.icon,
    required this.active,
    required this.theme,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = theme.colors;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: active ? colors.primary : colors.border, width: 1.5),
        ),
        child: Row(children: [
          Icon(icon, size: 20, color: active ? colors.primary : colors.muted),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: TextStyle(color: colors.ink, fontSize: 15, fontWeight: FontWeight.bold)),
              Text(body, style: TextStyle(color: colors.muted, fontSize: 13)),
            ]),
          ),
          if (active) Icon(Icons.check_circle, size: 20, color: colors.primary),
        ]),
      ),
    );
  }
}

extension _FirstOrNullExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
