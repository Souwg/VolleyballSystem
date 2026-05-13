import React from "react";

export const Select = ({ className = "", children, ...props }) => {
  return (
    <select className={`select ${className}`} {...props}>
      {children}
    </select>
  );
};
