import React from "react";

import sportflowIsotype from "../../img/isotipo-sportflow.svg";
import sportflowLogo from "../../img/sportflow-logo.svg";

import "../../styles/splash.css";

export const SplashScreen = () => {
  return (
    <div className="splash-screen" aria-label="Cargando SportFlow">
      <div className="splash-screen__content">
        <img src={sportflowIsotype} alt="" className="splash-screen__isotype" />

        <img
          src={sportflowLogo}
          alt="SportFlow"
          className="splash-screen__logo"
        />

        <p className="splash-screen__subtitle">Gestión deportiva para clubes</p>

        <div className="splash-screen__loader" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  );
};
