import React from "react";
import "../../../styles/attendanceToggle.css";

const STATES = ["present", "late", "absent"];

export const AttendanceToggle = ({ value, onChange, disabled = false }) => {
  const handleClick = () => {
    if (disabled) return;

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
      disabled={disabled}
      aria-label={disabled ? "Asistencia en modo lectura" : "Cambiar asistencia"}
    >
      {getIcon()}
    </button>
  );
};
