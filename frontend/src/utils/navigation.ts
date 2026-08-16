import type { useRouter } from "expo-router";

type Router = ReturnType<typeof useRouter>;

// router.back() throws "GO_BACK not handled" and leaves the screen stuck whenever
// there's no history to pop — e.g. the user landed here via a page refresh or a
// direct URL, not by navigating from within the app. Always fall back to a known
// route instead of assuming a back stack exists.
export function safeBack(router: Router, fallback: Parameters<Router["replace"]>[0]) {
  if (router.canGoBack()) router.back();
  else router.replace(fallback);
}
