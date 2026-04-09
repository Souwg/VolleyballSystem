import React from "react";
import { Button } from "./button";

export const StatCounter = ({ label, value, onChange }) => {
  const decrease = () => {
    if (value <= 0) return;
    onChange(value - 1);
  };

  const increase = () => {
    onChange(value + 1);
  };

  return (
    <div className="d-flex align-items-center justify-content-between mb-3">
      <span>{label}</span>

      <div className="d-flex align-items-center gap-2">
        <Button variant="secondary" onClick={decrease}>
          -
        </Button>

        <strong style={{ minWidth: "24px", textAlign: "center" }}>
          {value}
        </strong>

        <Button variant="primary" onClick={increase}>
          +
        </Button>
      </div>
    </div>
  );
};
