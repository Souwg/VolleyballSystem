import React from "react";

export const Container = ({ children }) => {
  return (
    <div
      style={{
        maxWidth: "1100px",
        margin: "0 auto",
        padding: "16px",
      }}
    >
      {children}
    </div>
  );
};
