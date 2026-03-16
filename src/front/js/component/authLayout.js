import React from "react";
import "../../styles/auth.css";
import hero from "../../img/volleyball-hero.jpg";

export const AuthLayout = ({ title, subtitle, children }) => {
  return (
    <div className="auth-page">
      {/* HERO IMAGE */}
      <div className="auth-hero" style={{ backgroundImage: `url(${hero})` }}>
        <div className="auth-hero-content">
          <span className="auth-badge">SPORTFLOW</span>

          <h1>Volleyball System</h1>

          <p>Plataforma inteligente de gestión de clubes deportivos.</p>

          <div className="auth-tags">
            <span>Players</span>
            <span>Teams</span>
            <span>Analytics</span>
          </div>
        </div>
      </div>

      {/* LOGIN PANEL */}
      <div className="auth-panel">
        <div className="auth-card">
          <h2>{title}</h2>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
};
