import React from "react";
import { createRoot } from "react-dom/client";
import Portal from "./Portal";
import "./dashboard.css";
import "./refinement.css";
import "./experience.css";
import "./workbench.css";
import "./brand.css";
import "./login.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Portal />
  </React.StrictMode>,
);
