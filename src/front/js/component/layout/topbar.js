import React from "react";
import isotipoSportflow from "../../../img/isotipo-sportflow.svg";

export const Topbar = ({ title, openMenu, isDetailPage = false }) => {
  return (
    <header className={`topbar ${isDetailPage ? "topbar-neutral" : ""}`}>
      <button
        className="topbar-menu-button"
        onClick={openMenu}
        aria-label="Abrir menú"
        type="button"
      >
        <span className="topbar-menu-icon" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </button>

      <div className="topbar-brand">
        <img
          src={isotipoSportflow}
          alt={title || "SportFlow"}
          className="topbar-logo"
        />
      </div>

      <div className="topbar-spacer" />
    </header>
  );
};
