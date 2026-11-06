import React from "react";
import { createRoot } from "react-dom/client";
import App from "./Dashboard";
import SignedFeedback from "./SignedFeedback";
import "./dashboard.css";
import "./refinement.css";
import "./experience.css";
import "./workbench.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
    <SignedFeedback />
  </React.StrictMode>,
);
