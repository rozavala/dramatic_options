import React from "react";
import ReactDOM from "react-dom/client";

// Self-hosted fonts (I3) — bundled into the build so the dashboard renders identically on an air-gapped /
// no-egress host (no Google Fonts CDN dependency). Weights 400/500/700 match the prior CDN request.
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@fontsource/roboto-mono/400.css";
import "@fontsource/roboto-mono/500.css";
import "@fontsource/roboto-mono/700.css";

import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Installable app: register the service worker (shell only — /api is never cached) and title the window by
// environment from the manifest, so an installed DEV and PROD are never confused. Production build only.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  fetch("/manifest.webmanifest")
    .then((r) => (r.ok ? r.json() : null))
    .then((m) => {
      if (m && typeof m.name === "string") document.title = `${m.name} — observability`;
    })
    .catch(() => {});
}
