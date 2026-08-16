import { useEffect, useState } from "react";

// Used to gate the "reenviar código" button behind a short cooldown.
export function useCountdown() {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (remaining <= 0) return;
    const id = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(id);
  }, [remaining]);

  return { remaining, restart: (seconds: number) => setRemaining(seconds) };
}
