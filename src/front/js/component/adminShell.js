import React, { useState, useContext } from "react";
import { Context } from "../store/appContext";
import { Navigate, useNavigate, Outlet } from "react-router-dom";

import { Sidebar } from "./layout/sidebar";
import { Topbar } from "./layout/topbar";
import { Container } from "./ui/container";
import { getRoleLandingPath } from "./roleRedirect";

export const AdminShell = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const navItems = [{ name: "Clients", path: "/admin/clients" }];

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

  if (store.user?.role !== "system_admin") {
    return (
      <Navigate to={getRoleLandingPath(store.user?.role)} replace />
    );
  }

  return (
    <div className="app-shell">
      {menuOpen && <div className="sidebar-overlay" onClick={closeMenu} />}

      <Sidebar
        title="SportFlow Admin"
        navItems={navItems}
        menuOpen={menuOpen}
        closeMenu={closeMenu}
        handleLogout={handleLogout}
      />

      <div className="main">
        <Topbar title="Volleyball Admin" openMenu={() => setMenuOpen(true)} />

        <main className="content">
          <Container>
            <Outlet />
          </Container>
        </main>
      </div>
    </div>
  );
};
