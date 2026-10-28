import React, { useState, useContext } from "react";
import { Context } from "../store/appContext";
import { Navigate, useNavigate, Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./layout/sidebar";
import { Topbar } from "./layout/topbar";
import { Container } from "./ui/container";
import { getRoleLandingPath } from "./roleRedirect";

const defaultNavItems = [
  { name: "Panel", path: "/dashboard" },
  { name: "Jugadores", path: "/players" },
  { name: "Categorías", path: "/categories" },
  { name: "Entrenamientos", path: "/trainings" },
  { name: "Partidos", path: "/matches" },
  { name: "Torneos", path: "/tournaments" },
  { name: "Pagos", path: "/payments" },
];

const coachNavItems = defaultNavItems.filter(
  (item) => item.path !== "/payments"
);

const ownerNavItems = [
  ...defaultNavItems,
  { name: "Usuarios", path: "/club/users" },
];

const staffNavItems = [
  { name: "Panel", path: "/dashboard" },
  { name: "Pagos", path: "/payments" },
  { name: "Jugadores", path: "/players" },
  { name: "Perfil del Club", path: "/club/profile" },
];

const isStaffAllowedPath = (pathname) =>
  pathname === "/dashboard" ||
  pathname === "/payments" ||
  pathname === "/payments/tournament-charges" ||
  pathname === "/players" ||
  pathname === "/club/profile" ||
  /^\/players\/[^/]+$/.test(pathname) ||
  /^\/players\/[^/]+\/payments$/.test(pathname);

const isCoachRestrictedPath = (pathname) =>
  pathname === "/payments" ||
  pathname === "/payments/tournament-charges" ||
  /^\/players\/[^/]+\/payments$/.test(pathname);

const isClubUsersPath = (pathname) => /^\/club\/users\/?$/.test(pathname);

export const AppShell = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const location = useLocation();

  const isDetailPage =
    location.pathname === "/club/profile" ||
    isClubUsersPath(location.pathname) ||
    /^\/categories\/[^/]+$/.test(location.pathname) ||
    /^\/tournaments\/[^/]+$/.test(location.pathname) ||
    /^\/tournament-teams\/[^/]+$/.test(location.pathname) ||
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
    location.pathname === "/payments/tournament-charges" ||
    /^\/match-players\/[^/]+\/stats$/.test(location.pathname);

  const isStaff = store.user?.role === "staff";
  const isCoach = store.user?.role === "coach";
  const isSystemAdmin = store.user?.role === "system_admin";
  const isClubOwner = store.user?.role === "club_owner";
  const navItems = isStaff
    ? staffNavItems
    : isCoach
    ? coachNavItems
    : isClubOwner
    ? ownerNavItems
    : [];
  const homePath = getRoleLandingPath(store.user?.role);

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

  const club = store.club || store.user?.club;

  if (isSystemAdmin) {
    return <Navigate to={homePath} replace />;
  }

  if (isStaff && !isStaffAllowedPath(location.pathname)) {
    return <Navigate to={homePath} replace />;
  }

  if (isCoach && isCoachRestrictedPath(location.pathname)) {
    return <Navigate to={homePath} replace />;
  }

  if (!isClubOwner && isClubUsersPath(location.pathname)) {
    return <Navigate to={homePath} replace />;
  }

  return (
    <div className="app-shell">
      {menuOpen && <div className="sidebar-overlay" onClick={closeMenu} />}

      <Sidebar
        title="SportFlow"
        club={club}
        navItems={navItems}
        homePath={homePath}
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
