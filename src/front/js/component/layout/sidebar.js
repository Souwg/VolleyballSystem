import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "../ui/button";

export const Sidebar = ({
  menuOpen,
  closeMenu,
  navItems,
  handleLogout,
  title,
}) => {
  const location = useLocation();

  return (
    <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
      <div className="sidebar-title">{title}</div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={closeMenu}
              className={`sidebar-link ${isActive ? "active" : ""}`}
            >
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <Button variant="secondary" onClick={handleLogout}>
          Logout
        </Button>
      </div>
    </aside>
  );
};
