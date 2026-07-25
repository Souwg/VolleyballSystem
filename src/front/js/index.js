//import react into the bundle
import React from "react";
import ReactDOM from "react-dom";
import { ToastProvider } from "../../context/toastContext";
//include your index.scss file into the bundle
import "../styles/index.css";
import "../styles/ui.css";
import "../styles/layout.css";

//import your own components
import Layout from "./layout";

//render your react application
ReactDOM.render(
  <ToastProvider>
    <Layout />
  </ToastProvider>,
  document.querySelector("#app"),
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((registration) => {
        console.info(
          "✅ Service worker registrado:",
          registration.scope,
        );
      })
      .catch((error) => {
        console.error(
          "❌ No se pudo registrar el service worker:",
          error,
        );
      });
  });
}
