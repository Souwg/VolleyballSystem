import React, { useState } from "react";
import { useContext } from "react";
import { Context } from "../store/appContext";
import { useNavigate } from "react-router-dom";
import { Link, useLocation } from "react-router-dom";

export const AppShell = ({ children }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login");
  };

  const closeMenu = () => setMenuOpen(false);

  const navItems = [
    { name: "Dashboard", path: "/dashboard" },
    { name: "Teams", path: "/teams" },
    { name: "Players", path: "/players" },
  ];

  return (
    <div
      className="d-flex"
      style={{ minHeight: "100vh", backgroundColor: "#f8f9fa" }}
    >
      {menuOpen && (
        <div
          onClick={closeMenu}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.35)",
            zIndex: 1040,
          }}
        />
      )}

      <div
        style={{
          width: "260px",
          maxWidth: "80%",
          backgroundColor: "#ffffff",
          borderRight: "1px solid #e9ecef",
          position: "fixed",
          top: 0,
          left: menuOpen ? 0 : "-260px",
          height: "100vh",
          zIndex: 1050,
          transition: "left 0.3s ease",
          padding: "1rem",
        }}
      >
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h5 className="mb-0">Volleyball System</h5>
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={closeMenu}
          >
            ✕
          </button>
        </div>

        <div className="d-flex flex-column gap-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={closeMenu}
                className={`btn text-start ${
                  isActive ? "btn-dark" : "btn-light"
                }`}
              >
                {item.name}
              </Link>
            );
          })}
        </div>
        <div className="mt-4 pt-3 border-top">
          <button
            className="btn btn-outline-danger w-100"
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </div>

      <div className="flex-grow-1" style={{ width: "100%" }}>
        <header
          className="d-flex align-items-center justify-content-between px-3 py-3 bg-white border-bottom"
          style={{ position: "sticky", top: 0, zIndex: 1030 }}
        >
          <div className="d-flex align-items-center gap-2">
            <button
              className="btn btn-outline-dark"
              onClick={() => setMenuOpen(true)}
            >
              ☰
            </button>
            <h6 className="mb-0">Volleyball System</h6>
          </div>
        </header>

        <main className="p-3">{children}</main>
      </div>
    </div>
  );
};
