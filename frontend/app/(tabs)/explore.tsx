// Kept as a real route so every existing router.push("/(tabs)/explore") call
// (Home, Messages, Activity empty states) keeps working — it's just no longer a
// bottom-bar icon. The actual UI now lives in BrowseOrders so the Pedidos tab's
// Prestador mode can reuse it without duplicating the filter/search logic.
export { default } from "@/src/components/BrowseOrders";
