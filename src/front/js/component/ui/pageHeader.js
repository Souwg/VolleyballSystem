import React from "react";

export const PageHeader = ({
  title,
  subtitle,
  actions,
  eyebrow,
  className = "",
  variant = "default",
  backTo,
  onBack,
}) => {
  return (
    <header className={`page-header page-header-${variant} ${className}`}>
      <div className="page-header-content">
        {(backTo || onBack) && (
          <button type="button" className="page-back-button" onClick={onBack}>
            ← Volver
          </button>
        )}

        {eyebrow && <span className="page-eyebrow">{eyebrow}</span>}

        <div>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>

      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
};
