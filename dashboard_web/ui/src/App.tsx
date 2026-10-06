import { useMemo } from "react";

import { DesktopConsole } from "./components/DesktopConsole";
import { fromBackend } from "./data/adapter";
import { useIsMobile } from "./data/useIsMobile";
import { useSnapshot } from "./data/useSnapshot";
import { MobileApp } from "./mobile/MobileApp";

// One fetch, two layouts: the 252px-rail desktop console, or the bottom-tab mobile app on narrow viewports.
export default function App() {
  const { snapshot, loading, error, refresh } = useSnapshot();
  const isMobile = useIsMobile();
  const fatal = snapshot?._fatal ?? null;
  const vm = useMemo(() => (snapshot && !snapshot._fatal ? fromBackend(snapshot) : null), [snapshot]);
  const props = { vm, loading, error, fatal, refresh };
  return isMobile ? <MobileApp {...props} /> : <DesktopConsole {...props} />;
}
