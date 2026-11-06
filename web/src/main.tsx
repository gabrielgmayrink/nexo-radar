import React from "react";
import { createRoot } from "react-dom/client";
import Portal from "./Portal";
import "./theme.css";
import "./dashboard.css";
import "./refinement.css";
import "./experience.css";
import "./workbench.css";
import "./login.css";
import "./usability.css";
import "./brand.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Portal />
  </React.StrictMode>,
);
