import React from "react";
import ReactDOM from "react-dom/client";
import App, { Disclaimer } from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary
      fallback={() => (
        <div>
          <Disclaimer />
          <p role="alert" className="p-6 text-sm text-gray-700">
            The app failed to load. Please reload the page.
          </p>
        </div>
      )}
    >
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
