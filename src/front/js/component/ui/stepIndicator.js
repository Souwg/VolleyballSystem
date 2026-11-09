import React from "react";
export const StepIndicator = ({ step, labels = [] }) => {
  return (
    <ol className="step-indicator" aria-label="Progreso de la configuración">
      {labels.map((label, index) => (
        <li
          key={label}
          className={`step ${
            step > index + 1
              ? "step-completed"
              : step === index + 1
              ? "step-current"
              : "step-pending"
          }`}
          aria-current={step === index + 1 ? "step" : undefined}
        >
          <span className="step-number" aria-hidden="true">
            {step > index + 1 ? "✓" : index + 1}
          </span>
          <span className="step-label">{label}</span>
        </li>
      ))}
    </ol>
  );
};
