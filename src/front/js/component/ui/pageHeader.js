import React from "react";

export const PageHeader = ({ title, subtitle }) => {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
};
