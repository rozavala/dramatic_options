import { useEffect, useState } from "react";

/** True on narrow (phone) viewports — switches the app between the desktop console and the mobile layout. */
export function useIsMobile(query = "(max-width: 760px)"): boolean {
  const [match, setMatch] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setMatch(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);
  return match;
}
