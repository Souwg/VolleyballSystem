import React from "react";
import logo from "../../../img/sportflow-logo.svg";

export const Topbar = ({ title, openMenu, isDetailPage = false }) => {
  return (
    <header className={`topbar ${isDetailPage ? "topbar-neutral" : ""}`}>
      <button className="topbar-menu-button" onClick={openMenu}>
        ☰
      </button>

      <div className="topbar-brand">
        <img src={logo} alt={title} className="topbar-logo" />
      </div>
    </header>
  );
};
