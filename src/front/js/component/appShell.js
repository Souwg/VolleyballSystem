import React, { useState, useContext } from "react";
import { Context } from "../store/appContext";
import { useNavigate, Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./layout/sidebar";
import { Topbar } from "./layout/topbar";
import { Container } from "./ui/container";

export const AppShell = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { actions } = useContext(Context);
  const navigate = useNavigate();
  const location = useLocation();

  const isDetailPage =
    /^\/players\/[^/]+$/.test(location.pathname) ||
    /^\/teams\/[^/]+$/.test(location.pathname) ||
    /^\/trainings\/[^/]+$/.test(location.pathname) ||
    /^\/matches\/[^/]+$/.test(location.pathname);

  const navItems = [
    { name: "Panel", path: "/dashboard" },
    { name: "Categorías", path: "/teams" },
    { name: "Jugadores", path: "/players" },
    { name: "Entrenamientos", path: "/trainings" },
  ];

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="app-shell">
      {menuOpen && <div className="sidebar-overlay" onClick={closeMenu} />}

      <Sidebar
        title="Volleyball System"
        navItems={navItems}
        menuOpen={menuOpen}
        closeMenu={closeMenu}
        handleLogout={handleLogout}
      />

      <div className="main">
        <Topbar title="Volleyball System" openMenu={() => setMenuOpen(true)} />

        <main className={`content ${isDetailPage ? "content-neutral" : ""}`}>
          <Container>
            <Outlet />
          </Container>
        </main>
      </div>
    </div>
  );
};
