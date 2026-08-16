import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, Alert, Platform, Pressable, ScrollView, Text, View } from "react-native";
import Animated, { FadeIn, ZoomIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, newIdempotencyKey, Order, Payment, Proposal } from "@/src/api";
import { Avatar, Btn, Chip, EmptyState, Field, Sheet, Stars } from "@/src/components/ui";
import { fonts } from "@/src/hooks/use-app-fonts";
import { useRequireAuth } from "@/src/hooks/use-require-auth";
import { useApp } from "@/src/state";
import { radius, space, type, useTheme } from "@/src/theme";
import { safeBack } from "@/src/utils/navigation";

const FIELD_LABELS: Record<string, string> = { origem: "De onde", destino: "Para onde", local_compra: "Onde comprar", equipamento: "Equipamento", veiculo: "Veículo", pet: "Pet", prazo: "Prazo", ambiente: "Ambiente/item", documento: "Documento", evento: "Evento" };
const REPORT_REASONS = ["Golpe ou fraude", "Conteúdo inadequado", "Pedido falso", "Comportamento abusivo", "Outro"];
const DISPUTE_REASONS = ["Serviço não foi realizado", "Cobrança indevida", "Comportamento do outro lado", "Qualidade do serviço", "Outro"];
const PAYMENT_STATUS_LABELS: Record<string, string> = { pending: "Processando pagamento", held: "Pagamento protegido", released: "Pagamento liberado", refunded: "Pagamento reembolsado" };

export default function OrderDetail() {
  const { colors } = useTheme();
  const { me } = useApp();
  useRequireAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id, published } = useLocalSearchParams<{ id: string; published?: string }>();

  const [order, setOrder] = useState<Order | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [favorited, setFavorited] = useState(false);
  const [showBanner, setShowBanner] = useState(published === "1");

  const [proposalOpen, setProposalOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [eta, setEta] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState(REPORT_REASONS[0]);
  const [reportDetails, setReportDetails] = useState("");

  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [paying, setPaying] = useState(false);

  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState(DISPUTE_REASONS[0]);
  const [disputeDetails, setDisputeDetails] = useState("");

  const [stars, setStars] = useState(0);
  const [reviewComment, setReviewComment] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.get(`/orders/${id}`);
      setOrder(data);
      const props = await api.get(`/orders/${id}/proposals`);
      setProposals(props);
      const favs = await api.get(`/favorites`);
      setFavorited((favs.order_ids || []).includes(id));
      if (["accepted", "in_progress", "completed", "cancelled"].includes(data.status)) {
        api.get(`/orders/${id}/payment`).then(setPayment).catch(() => setPayment(null));
      }
    } catch { /* order may be gone */ }
  }, [id, me]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!order || !me) {
    return <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}><ActivityIndicator color={colors.primary} /></View>;
  }

  const isOwner = me.id === order.client_id;
  const isWorker = me.id === order.worker_id;
  const myProposal = proposals.find((p) => p.worker_id === me.id);
  const hasReviewed = isOwner ? order.reviewed_by_client : order.reviewed_by_worker;
  const reviewTarget = isOwner ? order.worker : order.client;

  const haptic = () => { if (Platform.OS !== "web") Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); };

  const toggleFavorite = async () => {
    haptic();
    setFavorited(!favorited);
    try { await api.post("/favorites/toggle", { order_id: order.id }); } catch { setFavorited(favorited); }
  };

  const sendProposal = async () => {
    if (!amount) return;
    setSending(true);
    try {
      await api.post(`/orders/${order.id}/proposals`, { amount: Number(amount), message, eta });
      setProposalOpen(false);
      setAmount(""); setEta(""); setMessage("");
      haptic();
      load();
    } catch (e: any) { Alert.alert("Ops", e.message); } finally { setSending(false); }
  };

  const acceptProposal = async (proposal: Proposal) => {
    try {
      await api.post(`/proposals/${proposal.id}/accept`);
      haptic();
      load();
    } catch (e: any) { Alert.alert("Ops", e.message); }
  };

  const changeStatus = async (action: "start" | "complete" | "cancel") => {
    try {
      await api.post(`/orders/${order.id}/${action}`);
      haptic();
      load();
    } catch (e: any) { Alert.alert("Ops", e.message); }
  };

  const sendReview = async () => {
    if (!stars || !reviewTarget) return;
    setSending(true);
    try {
      await api.post("/reviews", { order_id: order.id, to_id: reviewTarget.id, stars, comment: reviewComment });
      haptic();
      load();
    } catch (e: any) { Alert.alert("Ops", e.message); } finally { setSending(false); }
  };

  const sendReport = async () => {
    setSending(true);
    try {
      await api.post("/reports", { target_type: "order", target_id: order.id, reason: reportReason, details: reportDetails });
      setReportOpen(false); setReportDetails("");
      Alert.alert("Denúncia enviada", "Nossa equipe vai analisar. Obrigado por ajudar a manter o FAZÊ seguro.");
    } catch { Alert.alert("Ops", "Não conseguimos enviar agora."); } finally { setSending(false); }
  };

  const payOrder = async () => {
    setPaying(true);
    try {
      const result = await api.post(`/orders/${order.id}/pay`, { method: "wallet" }, { "Idempotency-Key": newIdempotencyKey() });
      setPayment(result);
      setCheckoutOpen(false);
      haptic();
      load();
    } catch (e: any) {
      Alert.alert("Não foi possível pagar", e.message || "Confira seu saldo e tente novamente.");
    } finally { setPaying(false); }
  };

  const sendDispute = async () => {
    setSending(true);
    try {
      await api.post("/disputes", { target_type: "service", order_id: order.id, reason: disputeReason, description: disputeDetails });
      setDisputeOpen(false); setDisputeDetails("");
      Alert.alert("Registrado", "Recebemos seu relato e vamos analisar em breve.");
    } catch (e: any) { Alert.alert("Ops", e.message || "Não conseguimos enviar agora."); } finally { setSending(false); }
  };

  const otherUser = isOwner ? order.worker : order.client;
  const statusIndex = { accepted: 0, in_progress: 1, completed: 2 }[order.status] ?? -1;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, paddingTop: insets.top + 8 }}>
      {/* Header */}
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 20, height: 48, gap: 16 }}>
        <Pressable testID="order-back-button" onPress={() => safeBack(router, "/(tabs)/home")} hitSlop={10}><Ionicons name="arrow-back" size={24} color={colors.ink} /></Pressable>
        <Text style={{ flex: 1, color: colors.ink, fontSize: 16, fontWeight: "700" }}>Pedido</Text>
        <Pressable testID="favorite-button" onPress={toggleFavorite} hitSlop={8}>
          <Ionicons name={favorited ? "heart" : "heart-outline"} size={22} color={favorited ? colors.danger : colors.ink} />
        </Pressable>
        <Pressable testID="report-button" onPress={() => setReportOpen(true)} hitSlop={8}>
          <Ionicons name="flag-outline" size={20} color={colors.ink} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 48 }} showsVerticalScrollIndicator={false}>
        {showBanner && (
          <Pressable onPress={() => setShowBanner(false)} style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: colors.greenSoft, borderRadius: 14, padding: 14, marginBottom: 16 }}>
            <Ionicons name="checkmark-circle" size={20} color={colors.green} />
            <Text style={{ color: colors.green, fontWeight: "700", fontSize: 14, flex: 1 }}>Pedido publicado! Agora é só aguardar as propostas.</Text>
          </Pressable>
        )}

        {/* Title block */}
        <View style={{ flexDirection: "row", gap: 8, marginBottom: 10 }}>
          <View style={{ backgroundColor: colors.primarySoft, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, flexDirection: "row", alignItems: "center", gap: 5 }}>
            <Ionicons name={(order.category?.icon || "sparkles-outline") as keyof typeof Ionicons.glyphMap} size={13} color={colors.primary} />
            <Text style={{ color: colors.primary, fontSize: 12, fontWeight: "700" }}>{order.subcategory || order.category?.name}</Text>
          </View>
          <View style={{ backgroundColor: colors.alt, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
            <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "600" }}>{order.type === "favor" ? "Favor" : "Serviço"}</Text>
          </View>
        </View>
        <Text style={{ color: colors.ink, fontFamily: fonts.headingExtraBold, fontSize: 23, letterSpacing: -0.5 }}>{order.title}</Text>
        {order.description ? <Text style={{ color: colors.muted, fontSize: 14, lineHeight: 21, marginTop: 8 }}>{order.description}</Text> : null}

        {/* Info */}
        <View style={{ marginTop: 18, gap: 2 }}>
          <InfoRow icon="location-outline" text={`${order.neighborhood || ""}${order.city ? ` · ${order.city}` : ""} · localização aproximada`} />
          <InfoRow icon="calendar-outline" text={`${order.date_label}${order.time_label ? ` · ${order.time_label}` : ""}`} />
          {Object.entries(order.fields || {}).filter(([, v]) => v).map(([key, value]) => (
            <InfoRow key={key} icon="information-circle-outline" text={`${FIELD_LABELS[key] || key}: ${value}`} />
          ))}
        </View>

        {/* Budget */}
        <Animated.View key={`budget-${order.status}`} entering={FadeIn.duration(220)} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 16, marginTop: 16 }}>
          <View>
            <Text style={{ color: colors.faint, fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.8 }}>{order.accepted_amount ? "Valor combinado" : "Orçamento"}</Text>
            <Text style={{ color: colors.green, fontFamily: fonts.headingExtraBold, fontSize: 26 }}>R$ {order.accepted_amount || order.budget}</Text>
          </View>
          <Text style={{ color: order.status === "completed" ? colors.green : colors.primary, fontSize: 13, fontWeight: "700" }}>{order.status_label}</Text>
        </Animated.View>

        {/* Payment status */}
        {payment && (
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, backgroundColor: payment.status === "held" ? colors.greenSoft : colors.alt, borderRadius: radius.md, padding: space.md, marginTop: space.md }}>
            <Ionicons name={payment.status === "held" ? "shield-checkmark" : payment.status === "released" ? "checkmark-circle" : "time-outline"} size={18} color={payment.status === "held" ? colors.green : colors.muted} />
            <View style={{ flex: 1 }}>
              <Text style={{ color: colors.ink, fontFamily: fonts.bodySemiBold, fontSize: 13 }}>{PAYMENT_STATUS_LABELS[payment.status] || payment.status}</Text>
              {payment.status === "held" && <Text style={{ color: colors.muted, fontSize: 11 }}>O valor fica protegido até a conclusão do serviço.</Text>}
            </View>
          </View>
        )}
        {isOwner && order.status === "accepted" && (!payment || payment.status === "pending") && (
          <Pressable testID="pay-order-button" onPress={() => setCheckoutOpen(true)} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, backgroundColor: colors.primarySoft, borderRadius: radius.md, padding: space.md, marginTop: space.md }}>
            <Ionicons name="card-outline" size={18} color={colors.primary} />
            <Text style={{ flex: 1, color: colors.primary, fontFamily: fonts.bodyBold, fontSize: 13 }}>Pagar agora para liberar o início do serviço</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.primary} />
          </Pressable>
        )}

        {/* Status timeline */}
        {statusIndex >= 0 && (
          <View style={{ flexDirection: "row", alignItems: "center", marginTop: 22, paddingHorizontal: 4 }}>
            {["Aceito", "Em andamento", "Concluído"].map((step, i) => (
              <React.Fragment key={step}>
                {i > 0 && <View style={{ flex: 1, height: 2, backgroundColor: i <= statusIndex ? colors.green : colors.border, marginHorizontal: 4 }} />}
                <Animated.View key={`step-${i}-${i <= statusIndex}`} entering={i <= statusIndex ? ZoomIn.duration(240) : undefined} style={{ alignItems: "center", gap: 5 }}>
                  <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: i <= statusIndex ? colors.green : colors.alt, alignItems: "center", justifyContent: "center" }}>
                    <Ionicons name={i < statusIndex || order.status === "completed" && i === 2 ? "checkmark" : "ellipse"} size={i <= statusIndex ? 13 : 8} color={i <= statusIndex ? "#FFF" : colors.faint} />
                  </View>
                  <Text style={{ color: i <= statusIndex ? colors.ink : colors.faint, fontSize: 11, fontWeight: "600" }}>{step}</Text>
                </Animated.View>
              </React.Fragment>
            ))}
          </View>
        )}

        {(isOwner || isWorker) && ["accepted", "in_progress", "completed"].includes(order.status) && (
          <Pressable testID="dispute-button" onPress={() => setDisputeOpen(true)} style={{ alignSelf: "flex-start", marginTop: space.md }} hitSlop={8}>
            <Text style={{ color: colors.faint, fontFamily: fonts.bodySemiBold, fontSize: 12 }}>Tenho um problema com este pedido</Text>
          </Pressable>
        )}

        {/* People */}
        {(isOwner ? order.worker : order.client) && (
          <View style={{ marginTop: 24 }}>
            <Text style={{ color: colors.ink, fontSize: 16, fontWeight: "800", marginBottom: 10 }}>{isOwner ? "Fazedor" : "Quem pediu"}</Text>
            <UserCard user={otherUser!} />
          </View>
        )}
        {/* Proposals (owner, published) */}
        {isOwner && order.status === "published" && (
          <View style={{ marginTop: 24 }}>
            <Text style={{ color: colors.ink, fontSize: 16, fontWeight: "800", marginBottom: 10 }}>Propostas ({proposals.length})</Text>
            {proposals.length === 0 ? (
              <EmptyState icon="mail-open-outline" title="Nenhuma proposta por enquanto." body="Quando alguém se interessar, ela aparecerá aqui." />
            ) : (
              <View style={{ gap: 10 }}>
                {proposals.map((proposal) => (
                  <View key={proposal.id} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 16, gap: 10 }}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                      <Avatar name={proposal.worker?.name} initials={proposal.worker?.initials} size={40} />
                      <View style={{ flex: 1 }}>
                        <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
                          <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{proposal.worker?.name}</Text>
                          {proposal.worker?.verified_identity && <Ionicons name="checkmark-circle" size={14} color={colors.green} />}
                        </View>
                        <Text style={{ color: colors.muted, fontSize: 12 }}>★ {proposal.worker?.rating} · {proposal.worker?.jobs_done} serviços</Text>
                      </View>
                      <View style={{ alignItems: "flex-end" }}>
                        <Text style={{ color: colors.green, fontSize: 17, fontWeight: "800" }}>R$ {proposal.amount}</Text>
                        {proposal.eta ? <Text style={{ color: colors.faint, fontSize: 11 }}>{proposal.eta}</Text> : null}
                      </View>
                    </View>
                    {proposal.message ? <Text style={{ color: colors.muted, fontSize: 13, lineHeight: 19 }}>{proposal.message}</Text> : null}
                    <Btn testID={`accept-proposal-${proposal.id}`} title="Aceitar" small onPress={() => acceptProposal(proposal)} />
                  </View>
                ))}
              </View>
            )}
            <View style={{ marginTop: 16, gap: 10 }}>
              <Btn testID="edit-order-button" title="Editar pedido" variant="secondary" icon="create-outline" onPress={() => router.push({ pathname: "/create", params: { orderId: order.id } })} />
              <Btn title="Cancelar pedido" variant="ghost" onPress={() => Alert.alert("Cancelar pedido", "Tem certeza?", [{ text: "Não" }, { text: "Sim, cancelar", style: "destructive", onPress: () => changeStatus("cancel") }])} />
            </View>
          </View>
        )}

        {/* Rating (completed) */}
        {order.status === "completed" && (isOwner || isWorker) && reviewTarget && (
          <View style={{ marginTop: 24, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 18, padding: 18, gap: 12 }}>
            {hasReviewed ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <Ionicons name="checkmark-circle" size={20} color={colors.green} />
                <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "600" }}>Avaliação enviada. Obrigado!</Text>
              </View>
            ) : (
              <>
                <Text style={{ color: colors.ink, fontSize: 17, fontWeight: "800" }}>Como foi sua experiência?</Text>
                <Text style={{ color: colors.muted, fontSize: 13 }}>Avalie {reviewTarget.name.split(" ")[0]}</Text>
                <Stars value={stars} size={30} onChange={setStars} />
                <Field value={reviewComment} onChangeText={setReviewComment} placeholder="Comentário (opcional)" multiline style={{ minHeight: 70, textAlignVertical: "top" }} testID="review-comment-input" />
                <Btn testID="send-review-button" title="Enviar avaliação" onPress={sendReview} disabled={!stars} loading={sending} />
              </>
            )}
          </View>
        )}
      </ScrollView>

      {/* Bottom CTA */}
      {(order.status === "published" && !isOwner) || ((isOwner || isWorker) && ["accepted", "in_progress"].includes(order.status)) ? (
        <View style={{ paddingHorizontal: 20, paddingTop: 12, paddingBottom: Math.max(insets.bottom, 16), borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg, gap: 10 }}>
          {order.status === "published" && !isOwner && (
            myProposal
              ? <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, height: 52, borderRadius: 16, backgroundColor: colors.greenSoft }}>
                  <Ionicons name="checkmark-circle" size={18} color={colors.green} />
                  <Text style={{ color: colors.green, fontWeight: "700" }}>Proposta enviada · R$ {myProposal.amount}</Text>
                </View>
              : <Btn testID="open-proposal-button" title="Enviar proposta" icon="send-outline" onPress={() => { setAmount(String(order.budget)); setProposalOpen(true); }} />
          )}
          {["accepted", "in_progress"].includes(order.status) && (isOwner || isWorker) && (
            <>
              {order.status === "accepted" && isWorker && <Btn testID="start-order-button" title="Iniciar serviço" icon="play" onPress={() => changeStatus("start")} />}
              {order.status === "in_progress" && isOwner && <Btn testID="complete-order-button" title="Deu tudo certo? Concluir" icon="checkmark" onPress={() => Alert.alert("Concluir serviço", "Confirmar que o serviço foi realizado?", [{ text: "Ainda não" }, { text: "Concluir", onPress: () => changeStatus("complete") }])} />}
              <Btn testID="open-chat-button" title="Abrir conversa" variant="secondary" icon="chatbubble-outline" onPress={() => router.push(`/chat/${order.id}`)} />
            </>
          )}
        </View>
      ) : null}

      {/* Proposal sheet */}
      <Sheet visible={proposalOpen} onClose={() => setProposalOpen(false)} title="Sua proposta">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <Field label="Valor (R$)" value={amount} onChangeText={(v) => setAmount(v.replace(/[^0-9]/g, ""))} keyboardType="numeric" testID="proposal-amount-input" />
          <Field label="Tempo estimado" value={eta} onChangeText={setEta} placeholder="Ex: Hoje até as 18h" testID="proposal-eta-input" />
          <Field label="Mensagem" value={message} onChangeText={setMessage} multiline placeholder="Diga por que você é a pessoa certa..." style={{ minHeight: 90, textAlignVertical: "top" }} testID="proposal-message-input" />
          <Btn testID="send-proposal-button" title={`Enviar proposta${amount ? ` · R$ ${amount}` : ""}`} onPress={sendProposal} disabled={!amount} loading={sending} />
        </View>
      </Sheet>

      {/* Report sheet */}
      <Sheet visible={reportOpen} onClose={() => setReportOpen(false)} title="Denunciar">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {REPORT_REASONS.map((reason) => <Chip key={reason} label={reason} active={reportReason === reason} onPress={() => setReportReason(reason)} />)}
          </View>
          <Field value={reportDetails} onChangeText={setReportDetails} multiline placeholder="Detalhes (opcional)" style={{ minHeight: 80, textAlignVertical: "top" }} />
          <Btn title="Enviar denúncia" variant="danger" onPress={sendReport} loading={sending} />
        </View>
      </Sheet>

      {/* Checkout sheet */}
      <Sheet visible={checkoutOpen} onClose={() => setCheckoutOpen(false)} title="Confirmar pagamento">
        <View style={{ gap: space.md, paddingVertical: space.md, paddingBottom: space.xxl }}>
          <View style={{ backgroundColor: colors.alt, borderRadius: radius.md, padding: space.lg, gap: space.sm }}>
            <CheckoutRow label="Serviço" value={order.title} />
            <CheckoutRow label="Prestador" value={order.worker?.name || "—"} />
            <View style={{ height: 1, backgroundColor: colors.border, marginVertical: space.xs }} />
            <CheckoutRow label="Valor combinado" value={`R$ ${(order.accepted_amount || 0).toFixed(2).replace(".", ",")}`} />
            <CheckoutRow label="Método" value="Saldo da carteira" />
            <View style={{ height: 1, backgroundColor: colors.border, marginVertical: space.xs }} />
            <CheckoutRow label="Total" value={`R$ ${(order.accepted_amount || 0).toFixed(2).replace(".", ",")}`} strong />
          </View>
          <Text style={{ color: colors.faint, fontSize: 12 }}>O valor fica protegido até você confirmar a conclusão do serviço.</Text>
          <Btn testID="confirm-payment-button" title={paying ? "Processando..." : `Pagar R$ ${(order.accepted_amount || 0).toFixed(2).replace(".", ",")}`} onPress={payOrder} loading={paying} />
        </View>
      </Sheet>

      {/* Dispute sheet */}
      <Sheet visible={disputeOpen} onClose={() => setDisputeOpen(false)} title="Tenho um problema">
        <View style={{ gap: 14, paddingVertical: 12, paddingBottom: 24 }}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {DISPUTE_REASONS.map((reason) => <Chip key={reason} testID={`dispute-reason-${reason}`} label={reason} active={disputeReason === reason} onPress={() => setDisputeReason(reason)} />)}
          </View>
          <Field value={disputeDetails} onChangeText={setDisputeDetails} multiline placeholder="Conte o que aconteceu..." style={{ minHeight: 90, textAlignVertical: "top" }} testID="dispute-details-input" />
          <Btn testID="send-dispute-button" title="Enviar" onPress={sendDispute} loading={sending} />
        </View>
      </Sheet>
    </View>
  );
}

function CheckoutRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.md }}>
      <Text style={{ color: colors.muted, fontSize: strong ? 15 : 13 }} numberOfLines={1}>{label}</Text>
      <Text style={{ color: colors.ink, fontFamily: strong ? fonts.headingBold : fonts.bodySemiBold, fontSize: strong ? 17 : 13, flexShrink: 1, textAlign: "right" }} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function InfoRow({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 8 }}>
      <Ionicons name={icon} size={17} color={colors.primary} />
      <Text style={{ color: colors.ink, fontSize: 14, flex: 1 }}>{text}</Text>
    </View>
  );
}

function UserCard({ user }: { user: NonNullable<Order["client"]> }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 14 }}>
      <Avatar name={user.name} initials={user.initials} size={44} />
      <View style={{ flex: 1, gap: 2 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
          <Text style={{ color: colors.ink, fontSize: 14, fontWeight: "700" }}>{user.name}</Text>
          {user.verified_identity && <Ionicons name="checkmark-circle" size={14} color={colors.green} />}
        </View>
        <Text style={{ color: colors.muted, fontSize: 12 }}>★ {user.rating} · {user.jobs_done} serviços · {user.level}</Text>
      </View>
    </View>
  );
}
