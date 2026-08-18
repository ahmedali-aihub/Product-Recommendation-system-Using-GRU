import { useEffect, useState } from "react";

// True once `loading` has stayed true for longer than `delayMs`. Used to
// show a "waking up the server" hint instead of an indefinite skeleton --
// the free-tier backend/database can take up to ~60-90s to cold-start, and
// a silent skeleton for that long reads as broken, not slow.
export function useSlowLoad(loading, delayMs = 3000) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!loading) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), delayMs);
    return () => clearTimeout(timer);
  }, [loading, delayMs]);

  return slow;
}
