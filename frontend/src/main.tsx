import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import ErrorBoundary from "./components/ErrorBoundary";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary fallbackTitle="CanineSense AI Application Workspace">
      <HashRouter>
        <App />
      </HashRouter>
    </ErrorBoundary>
  </React.StrictMode>
);

if (typeof window !== "undefined" && "serviceWorker" in navigator && window.location.protocol === "https:") {
  window.addEventListener("load", () => {
    // Relative registration ensures compatibility with repository subpaths (e.g. GitHub Pages)
    navigator.serviceWorker.register("./sw.js").catch(() => {
      /* ignore registration failures gracefully */
    });
  });
}
