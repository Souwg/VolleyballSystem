import React, { useState, useContext } from "react";
import { Context } from "../store/appContext";
import { useNavigate, Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./layout/sidebar";
import { Topbar } from "./layout/topbar";
import { Container } from "./ui/container";

export const AppShell = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const location = useLocation();

  const isDetailPage =
    location.pathname === "/club/profile" ||
    /^\/categories\/[^/]+$/.test(location.pathname) ||
    /^\/players\/[^/]+$/.test(location.pathname) ||
    /^\/players\/[^/]+\/edit$/.test(location.pathname) ||
    /^\/teams\/[^/]+$/.test(location.pathname) ||
    /^\/teams\/[^/]+\/trainings$/.test(location.pathname) ||
    /^\/teams\/[^/]+\/trainings\/new$/.test(location.pathname) ||
    /^\/teams\/[^/]+\/matches$/.test(location.pathname) ||
    /^\/teams\/[^/]+\/matches\/new$/.test(location.pathname) ||
    /^\/trainings\/[^/]+$/.test(location.pathname) ||
    /^\/matches\/[^/]+$/.test(location.pathname) ||
    /^\/matches\/[^/]+\/live$/.test(location.pathname) ||
    /^\/matches\/[^/]+\/stats$/.test(location.pathname) ||
    /^\/players\/[^/]+\/payments$/.test(location.pathname) ||
    /^\/match-players\/[^/]+\/stats$/.test(location.pathname);

  const navItems = [
    { name: "Panel", path: "/dashboard" },
    { name: "Jugadores", path: "/players" },
    { name: "Categorías", path: "/categories" },
    { name: "Entrenamientos", path: "/trainings" },
    { name: "Partidos", path: "/matches" },
    { name: "Pagos", path: "/payments" },
  ];

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

  const club = store.club || store.user?.club;

  return (
    <div className="app-shell">
      {menuOpen && <div className="sidebar-overlay" onClick={closeMenu} />}

      <Sidebar
        title="SportFlow"
        club={club}
        navItems={navItems}
        menuOpen={menuOpen}
        closeMenu={closeMenu}
        handleLogout={handleLogout}
      />

      <div className="main">
        <Topbar
          title="SportFlow"
          openMenu={() => setMenuOpen(true)}
          isDetailPage={isDetailPage}
        />

        <main className={`content ${isDetailPage ? "content-neutral" : ""}`}>
          <Container>
            <Outlet />
          </Container>
        </main>
      </div>
    </div>
  );
};
