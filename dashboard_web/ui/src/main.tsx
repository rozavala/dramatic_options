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
