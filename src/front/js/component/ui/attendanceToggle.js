import React from "react";

const STATES = ["present", "late", "absent"];

export const AttendanceToggle = ({ value, onChange }) => {
  const handleClick = () => {
    const index = STATES.indexOf(value);
    const next = index === -1 ? "present" : STATES[(index + 1) % STATES.length];

    onChange(next);
  };

  const getIcon = () => {
    if (value === "present") return "🟢";
    if (value === "late") return "🟡";
    if (value === "absent") return "🔴";
    return "⚪";
  };

  return (
    <button
      type="button"
      className={`attendance-toggle attendance-${value || "unmarked"}`}
      onClick={handleClick}
    >
      {getIcon()}
    </button>
  );
};
