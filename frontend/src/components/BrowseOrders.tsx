import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order } from "@/src/api";
import { OrderCard } from "@/src/components/OrderCard";
import { Btn, Chip, EmptyState, Sheet, Skeleton } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useBreakpoint } from "@/src/hooks/use-breakpoint";
import { useApp } from "@/src/state";
import { useTheme } from "@/src/theme";
const BUDGETS = [{ label: "Até R$ 30", value: 30 }, { label: "Até R$ 50", value: 50 }, { label: "Até R$ 100", value: 100 }, { label: "Até R$ 200", value: 200 }];
const PAGE_SIZE = 20;

// The "find work nearby" browse/search/filter UI. Lives here (not in a route file)
// so it can be reused both as the standalone /(tabs)/explore route (deep links into
// it keep working) and inside the Pedidos tab's Prestador-mode view.
export default function BrowseOrders() {
  const { colors } = useTheme();
  const { categories, neighborhoods, city } = useApp();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ category?: string }>();
  const { isDesktop, isTablet } = useBreakpoint();
  const numColumns = isDesktop ? 3 : isTablet ? 2 : 1;

  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [type, setType] = useState<string | null>(null);
  const [hood, setHood] = useState<string | null>(null);
  const [budget, setBudget] = useState<number | null>(null);
  const [urgent, setUrgent] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (params.category) setCategory(params.category);
  }, [params.category]);

  const buildQuery = (q: string, cat: string | null, tp: string | null, nb: string | null, bd: number | null, ur: boolean, offset: number) => {
    const parts = [`city_id=${city!.id}`, `status=published`, `limit=${PAGE_SIZE}`, `offset=${offset}`];
    if (q.trim()) parts.push(`q=${encodeURIComponent(q.trim())}`);
    if (cat) parts.push(`category_id=${cat}`);
    if (tp) parts.push(`type=${tp}`);
    if (nb) parts.push(`neighborhood_id=${nb}`);
    if (bd) parts.push(`max_budget=${bd}`);
    if (ur) parts.push(`urgent=true`);
    return parts.join("&");
  };

  const load = useCallback(async (q: string, cat: string | null, tp: string | null, nb: string | null, bd: number | null, ur: boolean) => {
    if (!city) return;
    setLoading(true);
    try {
      const data: Order[] = await api.get(`/orders?${buildQuery(q, cat, tp, nb, bd, ur, 0)}`);
      setOrders(data);
      setHasMore(data.length === PAGE_SIZE);
    } catch { setOrders([]); setHasMore(false); } finally { setLoading(false); }
  }, [city]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadMore = async () => {
    if (!city || loading || loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const data: Order[] = await api.get(`/orders?${buildQuery(search, category, type, hood, budget, urgent, orders.length)}`);
      setOrders((prev) => [...prev, ...data]);
      setHasMore(data.length === PAGE_SIZE);
    } catch { /* keep what's already loaded */ } finally { setLoadingMore(false); }
  };

  useFocusEffect(useCallback(() => { load(search, category, type, hood, budget, urgent); }, [load, category, type, hood, budget, urgent])); // eslint-disable-line react-hooks/exhaustive-deps

  const onSearch = (text: string) => {
    setSearch(text);
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load(text, category, type, hood, budget, urgent), 400);
  };

  const activeFilters = [type, hood, budget, urgent || null].filter(Boolean).length;
  const clearFilters = () => { setType(null); setHood(null); setBudget(null); setUrgent(false); };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 12 }}>
      {/* Header */}
      <View style={{ paddingHorizontal: 20, gap: 12, width: "100%", maxWidth: isDesktop ? 1200 : undefined, alignSelf: "center" }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <Ionicons name="location" size={15} color={colors.primary} />
          <Text style={{ color: colors.ink, fontFamily: fonts.bodyBold, fontSize: 15 }}>{city?.name || "Parauapebas"}, PA</Text>
        </View>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 24, letterSpacing: -0.5 }}>Pedidos perto de você</Text>
        <View style={{ flexDirection: "row", gap: 10 }}>
          <View style={{ flex: 1, flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 14, paddingHorizontal: 14, height: 48 }}>
            <Ionicons name="search-outline" size={17} color={colors.faint} />
            <TextInput
              testID="explore-search-input"
              value={search}
              onChangeText={onSearch}
              placeholder="Buscar tarefa ou serviço"
              placeholderTextColor={colors.faint}
              style={{ flex: 1, color: colors.ink, fontSize: 14, height: "100%" }}
            />
          </View>
          <Pressable testID="explore-filters-button" onPress={() => setFiltersOpen(true)} style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: activeFilters ? colors.ink : colors.surface, borderWidth: 1, borderColor: activeFilters ? colors.ink : colors.border, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="options-outline" size={19} color={activeFilters ? colors.bg : colors.ink} />
          </Pressable>
        </View>
      </View>

      {/* Category chips */}
      <View style={{ marginTop: 14 }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, gap: 8 }}>
          <Chip label="Todos" active={!category} onPress={() => setCategory(null)} />
          {categories.map((cat) => (
            <Chip key={cat.id} testID={`explore-cat-${cat.id}`} label={cat.name} active={category === cat.id} onPress={() => setCategory(category === cat.id ? null : cat.id)} />
          ))}
        </ScrollView>
      </View>

      {/* List */}
      {loading ? (
        <View style={{ padding: 20, gap: 10 }}><Skeleton /><Skeleton /><Skeleton /></View>
      ) : (
        <FlatList
          key={numColumns}
          data={orders}
          keyExtractor={(item) => item.id}
          numColumns={numColumns}
          columnWrapperStyle={numColumns > 1 ? { gap: 12 } : undefined}
          contentContainerStyle={{ padding: 20, paddingBottom: 40, gap: 12, maxWidth: isDesktop ? 1200 : undefined, width: "100%", alignSelf: "center" }}
          showsVerticalScrollIndicator={false}
          renderItem={({ item, index }) => <OrderCard order={item} index={index} style={numColumns > 1 ? { flex: 1 } : undefined} onPress={() => router.push(`/order/${item.id}`)} />}
          ListEmptyComponent={<EmptyState icon="leaf-outline" title="Nenhum pedido encontrado." body="Tente outra busca ou remova os filtros." actionTitle={activeFilters ? "Limpar filtros" : undefined} onAction={clearFilters} />}
          onEndReachedThreshold={0.4}
          onEndReached={loadMore}
          ListFooterComponent={loadingMore ? <ActivityIndicator style={{ marginTop: 12 }} color={colors.muted} /> : null}
        />
      )}

      {/* Filters sheet */}
      <Sheet visible={filtersOpen} onClose={() => setFiltersOpen(false)} title="Filtros">
        <View style={{ gap: 20, paddingVertical: 12, paddingBottom: 24 }}>
          <View style={{ gap: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 }}>Tipo</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Chip label="Todos" active={!type} onPress={() => setType(null)} />
              <Chip label="Favor" active={type === "favor"} onPress={() => setType("favor")} />
              <Chip label="Serviço" active={type === "servico"} onPress={() => setType("servico")} />
            </View>
          </View>
          <View style={{ gap: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 }}>Urgência</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Chip icon="flash" label="Preciso agora" active={urgent} onPress={() => setUrgent(!urgent)} />
            </View>
          </View>
          <View style={{ gap: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 }}>Valor</Text>
            <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
              {BUDGETS.map((b) => <Chip key={b.value} label={b.label} active={budget === b.value} onPress={() => setBudget(budget === b.value ? null : b.value)} />)}
            </View>
          </View>
          <View style={{ gap: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 }}>Bairro</Text>
            <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
              {neighborhoods.slice(0, 20).map((n) => <Chip key={n.id} label={n.name} active={hood === n.id} onPress={() => setHood(hood === n.id ? null : n.id)} />)}
            </View>
          </View>
          <Btn testID="apply-filters-button" title="Ver resultados" onPress={() => setFiltersOpen(false)} />
          {activeFilters > 0 && <Btn title="Limpar filtros" variant="ghost" onPress={() => { clearFilters(); setFiltersOpen(false); }} />}
        </View>
      </Sheet>
    </View>
  );
}
