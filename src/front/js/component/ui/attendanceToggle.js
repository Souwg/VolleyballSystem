import React from "react";
import "../../../styles/attendanceToggle.css";

const STATES = [
  { value: "present", label: "Presente" },
  { value: "late", label: "Tarde" },
  { value: "absent", label: "Ausente" },
];

export const AttendanceToggle = ({
  value,
  onChange,
  disabled = false,
  playerName = "deportista",
}) => (
  <div
    className="attendance-options"
    role="group"
    aria-label={`Asistencia de ${playerName}`}
  >
    {STATES.map((state) => {
      const selected = value === state.value;

      return (
        <button
          key={state.value}
          type="button"
          className={`attendance-option attendance-${state.value}`}
          onClick={() => onChange(state.value)}
          disabled={disabled}
          aria-pressed={selected}
          aria-label={`${playerName}: ${state.label}`}
        >
          {state.label}
        </button>
      );
    })}
  </div>
);
