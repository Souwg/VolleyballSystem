import React, { useState, useContext } from "react";
import { Context } from "../store/appContext";
import { useNavigate, Outlet } from "react-router-dom";

import { Sidebar } from "./layout/sidebar";
import { Topbar } from "./layout/topbar";
import { Container } from "./ui/container";

export const AdminShell = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const navItems = [{ name: "Clients", path: "/admin/clients" }];

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

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
