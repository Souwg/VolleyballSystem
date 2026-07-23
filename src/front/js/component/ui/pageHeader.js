import React from "react";
import { getAssetUrl } from "../../utils/getAssetUrl";

export const PageHeader = ({
  title,
  subtitle,
  actions,
  eyebrow,
  badge,
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

        <div
          className={`page-header-main ${
            showIcon ? "page-header-main-with-icon" : ""
          } ${showAvatar ? "page-header-main-with-avatar" : ""}`}
        >
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

          <div className="page-header-copy">
            {(eyebrow || badge) && (
              <div className="page-header-eyebrow-row">
                {eyebrow && <span className="page-eyebrow">{eyebrow}</span>}
                {badge}
              </div>
            )}

            <div className="page-header-text">
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>
        </div>
      </div>

      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
};
