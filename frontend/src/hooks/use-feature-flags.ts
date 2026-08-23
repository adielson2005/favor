// Thin selector over AppProvider's bootstrap-fed feature_flags — a flag toggled in
// the admin panel takes effect the next time bootstrap loads (app open/reload),
// no separate request and no app update needed. Defaults a flag to `true` (on)
// when the app hasn't heard from the backend yet, or the backend doesn't know
// about the key — new features stay usable rather than blinking off during boot.
import { useApp } from "@/src/state";

export function useFeatureFlag(key: string): boolean {
  const { featureFlags } = useApp();
  return featureFlags[key] !== false;
}
