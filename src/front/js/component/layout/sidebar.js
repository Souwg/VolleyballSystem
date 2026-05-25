import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "../ui/button";

export const Sidebar = ({
  menuOpen,
  closeMenu,
  navItems,
  handleLogout,
  title,
  club,
}) => {
  const location = useLocation();

  const getInitials = (value = "") => {
    return value
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word.charAt(0))
      .join("")
      .toUpperCase();
  };

  return (
    <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
      <Link to="/dashboard" onClick={closeMenu} className="sidebar-title">
        {title}
      </Link>

      {club && (
        <Link to="/dashboard" onClick={closeMenu} className="sidebar-club">
          <div className="sidebar-club-avatar">
            {club.image_url ? (
              <img src={club.image_url} alt={club.name} />
            ) : (
              <span>{getInitials(club.name)}</span>
            )}
          </div>

          <div className="sidebar-club-info">
            <strong>{club.name}</strong>
            <span>Club activo</span>
          </div>
        </Link>
      )}

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
          Cerrar sesión
        </Button>
      </div>
    </aside>
  );
};
