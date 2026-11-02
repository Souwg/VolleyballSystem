import React from "react";
import { Eye } from "lucide-react";

export const ReadOnlyNotice = ({ children, className = "" }) => (
  <div className={`read-only-notice ${className}`} role="note">
    <Eye size={17} aria-hidden="true" />
    <p>{children}</p>
  </div>
);

export const AssignedBadge = () => (
  <span className="status-badge status-info">Asignado</span>
);

export const ReadOnlyBadge = () => (
  <span className="status-badge status-muted">Solo consulta</span>
);
