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

  avatar,
  fallback,
}) => {
  const getInitials = (value = "") => {
    return value
      .split(" ")
      .slice(0, 2)
      .map((word) => word.charAt(0))
      .join("")
      .toUpperCase();
  };

  return (
    <header className={`page-header page-header-${variant} ${className}`}>
      <div className="page-header-content">
        {(backTo || onBack) && (
          <button type="button" className="page-back-button" onClick={onBack}>
            ← Volver
          </button>
        )}

        {avatar || fallback ? (
          <div className="page-header-avatar">
            {avatar ? (
              <img src={avatar} alt={title} />
            ) : (
              <span>{getInitials(fallback)}</span>
            )}
          </div>
        ) : null}

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
