import React from "react";

export const Input = ({ ...props }) => {
  return (
    <input
      {...props}
      style={{
        width: "100%",
        padding: "8px",
        borderRadius: "6px",
        border: "1px solid #ddd",
      }}
    />
  );
};
