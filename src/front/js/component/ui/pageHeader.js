import React from "react";
import { getAssetUrl } from "../../utils/getAssetUrl";

export const PageHeader = ({
  title,
  subtitle,
  actions,
  eyebrow,
  className = "",
  variant = "default",
  tone = "default",
  icon: Icon,
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

  const showAvatar = avatar || fallback;
  const showIcon = Icon && !showAvatar;

  return (
    <header
      className={`page-header page-header-${variant} page-header-tone-${tone} ${className}`}
    >
      <div className="page-header-content">
        {(backTo || onBack) && (
          <button type="button" className="page-back-button" onClick={onBack}>
            ← Volver
          </button>
        )}

        {showAvatar ? (
          <div className="page-header-avatar">
            {avatar ? (
              <img src={getAssetUrl(avatar)} alt={title} />
            ) : (
              <span>{getInitials(fallback)}</span>
            )}
          </div>
        ) : showIcon ? (
          <div className="page-header-icon">
            <Icon size={22} strokeWidth={2.4} />
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
