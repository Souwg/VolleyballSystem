import React from "react";
import "../../styles/auth.css";
import hero from "../../img/volleyball-hero.jpg";

export const AuthLayout = ({ title, subtitle, children }) => {
  return (
    <div className="auth-page" style={{ "--auth-hero-image": `url(${hero})` }}>
      <div className="auth-hero">
        <div className="auth-hero-content">
          <span className="auth-badge">SPORTFLOW</span>

          <h1>Volleyball System</h1>

          <p>Plataforma inteligente de gestión de clubes deportivos.</p>

          <div className="auth-tags">
            <span>Jugadoras</span>
            <span>Equipos</span>
            <span>Estadísticas</span>
          </div>
        </div>
      </div>

      <div className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand">
            <span>SPORTFLOW</span>
            <strong>Volleyball System</strong>
          </div>

          <h2>{title}</h2>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
};
