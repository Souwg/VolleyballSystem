import React from "react";

export const FormField = ({
  label,
  error,
  children,
  helper,
  htmlFor,
  errorId,
}) => {
  return (
    <div className="form-field">
      {label && (
        <label className="form-label" htmlFor={htmlFor}>
          {label}
        </label>
      )}

      {children}

      {helper && !error && <p className="form-helper">{helper}</p>}

      {error && (
        <p className="form-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
};
