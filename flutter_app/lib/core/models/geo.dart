// Mirrors frontend/src/api.ts's Category/Neighborhood/City/StateRef types
// field-for-field — same backend, same shape, both clients must agree.

class Subcategory {
  final String id;
  final String name;
  const Subcategory({required this.id, required this.name});

  factory Subcategory.fromJson(Map<String, dynamic> json) =>
      Subcategory(id: json['id'] as String, name: json['name'] as String);
}

class Category {
  final String id;
  final String name;
  final String icon;
  final bool active;
  final List<Subcategory> subcategories;

  const Category({
    required this.id,
    required this.name,
    required this.icon,
    required this.active,
    required this.subcategories,
  });

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        icon: json['icon'] as String,
        active: json['active'] as bool? ?? true,
        subcategories: (json['subcategories'] as List<dynamic>? ?? [])
            .map((s) => Subcategory.fromJson(s as Map<String, dynamic>))
            .toList(),
      );
}

class StateRef {
  final String id;
  final String name;
  final String uf;
  final bool active;
  const StateRef({required this.id, required this.name, required this.uf, required this.active});

  factory StateRef.fromJson(Map<String, dynamic> json) => StateRef(
        id: json['id'] as String,
        name: json['name'] as String,
        uf: json['uf'] as String,
        active: json['active'] as bool? ?? true,
      );
}

class City {
  final String id;
  final String name;
  final String stateId;
  final bool active;
  const City({required this.id, required this.name, required this.stateId, required this.active});

  factory City.fromJson(Map<String, dynamic> json) => City(
        id: json['id'] as String,
        name: json['name'] as String,
        stateId: json['state_id'] as String,
        active: json['active'] as bool? ?? true,
      );
}

class Neighborhood {
  final String id;
  final String name;
  final String kind;
  final String cityId;
  const Neighborhood({required this.id, required this.name, required this.kind, required this.cityId});

  factory Neighborhood.fromJson(Map<String, dynamic> json) => Neighborhood(
        id: json['id'] as String,
        name: json['name'] as String,
        kind: json['kind'] as String? ?? 'bairro',
        cityId: json['city_id'] as String,
      );
}
