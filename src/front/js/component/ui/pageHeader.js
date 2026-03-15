import React from "react";
export const PageHeader = ({ title }) => {
  return (
    <div style={{ marginBottom: "20px" }}>
      <h1
        style={{
          fontSize: "24px",
          fontWeight: "600",
        }}
      >
        {title}
      </h1>
    </div>
  );
};
