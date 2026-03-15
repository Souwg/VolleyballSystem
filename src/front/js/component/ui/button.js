import React from "react";
export const Button = ({ children, variant = "primary", ...props }) => {
  const styles = {
    padding: "8px 14px",
    borderRadius: "6px",
    border: "none",
    cursor: "pointer",
    fontWeight: "500",
    background: variant === "primary" ? "#111" : "#e9ecef",
    color: variant === "primary" ? "white" : "#111",
  };

  return (
    <button style={styles} {...props}>
      {children}
    </button>
  );
};
