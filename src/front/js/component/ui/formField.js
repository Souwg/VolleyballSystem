import React from "react";

export const FormField = ({ label, error, children, helper }) => {
  return (
    <div className="form-field">
      {label && <label className="form-label">{label}</label>}

      {children}

      {helper && !error && <p className="form-helper">{helper}</p>}

      {error && <p className="form-error">{error}</p>}
    </div>
  );
};
