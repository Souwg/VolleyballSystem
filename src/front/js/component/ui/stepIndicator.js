import React from "react";

export const StepIndicator = ({ step }) => {
  return (
    <div className="step-indicator">
      <div className={`step ${step >= 1 ? "active" : ""}`} />
      <div className={`step ${step >= 2 ? "active" : ""}`} />
      <div className={`step ${step >= 3 ? "active" : ""}`} />
    </div>
  );
};
