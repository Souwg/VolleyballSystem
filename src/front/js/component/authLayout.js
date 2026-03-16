import React from "react";
import "../../styles/auth.css";

export const AuthLayout = ({ title, subtitle, children }) => {
  return (
    <div className="auth-page">
      <div className="auth-wrapper">
        <div className="logo">
          <h1>SportFlow</h1>
        </div>

        <p className="subtitle">Volleyball club management</p>

        <div className="auth-card">
          <h2>{title}</h2>

          {subtitle && <p className="auth-subtitle">{subtitle}</p>}

          {children}
        </div>
      </div>
    </div>
  );
};
