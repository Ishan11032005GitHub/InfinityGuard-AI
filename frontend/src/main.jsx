import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import "./styles.css";

const root = document.getElementById("root");
root.innerHTML = '<div style="padding:24px;font-family:system-ui">Loading InfinityGuard AI...</div>';

try {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <ErrorBoundary>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ErrorBoundary>
    </React.StrictMode>
  );
} catch (error) {
  root.innerHTML = `<pre style="padding:24px;white-space:pre-wrap;color:#b91c1c;font-family:system-ui">${String(error?.message || error)}</pre>`;
}
