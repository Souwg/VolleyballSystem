import React from "react";
import isotipoSportflow from "../../../img/isotipo-sportflow.svg";
import wordmarkSportflow from "../../../img/sportflow-logo.svg";

export const Topbar = ({ openMenu, isDetailPage = false }) => {
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

      <div className="topbar-brand" aria-label="SportFlow">
        <img
          src={isotipoSportflow}
          alt=""
          aria-hidden="true"
          className="topbar-isotipo"
        />

        <img
          src={wordmarkSportflow}
          alt="SportFlow"
          className="topbar-wordmark"
        />
      </div>

      <div className="topbar-spacer" aria-hidden="true" />
    </header>
  );
};
