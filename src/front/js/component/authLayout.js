import React from "react";
import "../../styles/auth.css";

export const AuthLayout = ({ title, subtitle, children }) => {
  return (
    <div className="auth-container">
      <div className="auth-brand">
        <h1>SportFlow</h1>
        <p>Volleyball club management</p>
      </div>

      <div className="auth-card">
        <h2>{title}</h2>

        {subtitle && <p className="auth-subtitle">{subtitle}</p>}

        {children}
      </div>
    </div>
  );
};
