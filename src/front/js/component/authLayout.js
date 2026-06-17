import React from "react";
import "../../styles/auth.css";
import hero from "../../img/volleyball-hero.jpg";

import isotipo from "../../img/isotipo-sportflow.svg";
import sportflowLogo from "../../img/sportflow-logo.svg";

export const AuthLayout = ({
  title,
  subtitle,
  children,
  variant = "center",
}) => {
  return (
    <div
      className={`auth-page auth-page-${variant}`}
      style={{ "--auth-hero-image": `url(${hero})` }}
    >
      <div className="auth-hero">
        <div className="auth-hero-content">
          <div className="auth-brand">
            <img className="auth-brand-icon" src={isotipo} alt="SportFlow" />

            <img
              className="auth-brand-wordmark"
              src={sportflowLogo}
              alt="SportFlow"
            />
          </div>

          <h1>Gestión deportiva simple y moderna</h1>

          <p>
            Plataforma inteligente para organizar clubes, equipos, deportistas,
            entrenamientos, partidos y pagos.
          </p>

          <div className="auth-tags">
            <span>Deportistas</span>
            <span>Equipos</span>
            <span>Pagos</span>
          </div>
        </div>
      </div>

      <div className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand">
            <img
              className="auth-mobile-brand-icon"
              src={isotipo}
              alt="SportFlow"
            />

            <img
              className="auth-mobile-brand-wordmark"
              src={sportflowLogo}
              alt="SportFlow"
            />
          </div>

          <h2>{title}</h2>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
};
