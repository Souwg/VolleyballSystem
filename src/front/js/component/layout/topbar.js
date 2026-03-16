import React from "react";
import { Button } from "../ui/button";

export const Topbar = ({ title, openMenu }) => {
  return (
    <header className="topbar">
      <Button variant="secondary" className="menu-button" onClick={openMenu}>
        ☰
      </Button>

      <h4>{title}</h4>
    </header>
  );
};
