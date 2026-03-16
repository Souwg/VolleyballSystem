import React from "react";
export const StepIndicator = ({ step, total = 3 }) => {
  return (
    <div className="step-indicator">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className={`step ${step > i ? "active" : ""}`} />
      ))}
    </div>
  );
};
