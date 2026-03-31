import React from "react";

const STATES = ["present", "late", "absent"];

export const AttendanceToggle = ({ value, onChange }) => {
  const handleClick = () => {
    const index = STATES.indexOf(value);
    const next = STATES[(index + 1) % STATES.length];
    onChange(next);
  };

  return (
    <button
      className={`attendance-toggle attendance-${value}`}
      onClick={handleClick}
    >
      {value === "present" && "🟢"}
      {value === "late" && "🟡"}
      {value === "absent" && "🔴"}
    </button>
  );
};
