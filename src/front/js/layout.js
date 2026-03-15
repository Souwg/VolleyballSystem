import React, { useEffect, useState, useContext } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Context } from "./store/appContext";
import "../styles/layout.css";

import ScrollToTop from "./component/scrollToTop";
import { RoleRedirect } from "./component/roleRedirect";
import { BackendURL } from "./component/backendURL";
import { PublicRoute } from "./component/publicRoute";
import { ProtectedRoute } from "./component/protectedRoute";
import { OnboardingRoute } from "./component/onboardingRoute";

import { Clients } from "./pages/admin/clients";
import { Login } from "./pages/auth/login";
import { AppShell } from "./component/appShell";
import { AdminShell } from "./component/adminShell";
import { Dashboard } from "./pages/dashboard/dashboard";
import { SetPassword } from "./pages/auth/setPassword";
import { Onboarding } from "./pages/onboarding/onboarding";
import { Teams } from "./pages/teams/teams";
import { TeamDetail } from "./pages/teams/teamDetail";
import { Players } from "./pages/players/players";
import injectContext from "./store/appContext";

const Layout = () => {
  const basename = process.env.BASENAME || "";

  const { actions } = useContext(Context);

  const [loadingSession, setLoadingSession] = useState(true);

  useEffect(() => {
    const initSession = async () => {
      try {
        const restored = await actions.restoreSession();

        if (restored) {
          const user = JSON.parse(localStorage.getItem("user"));

          if (user?.role !== "system_admin") {
            await actions.getOnboardingStatus();
          }
        }
      } catch (err) {
        console.error("No se pudo restaurar sesión:", err);
      } finally {
        setLoadingSession(false);
      }
    };

    initSession();
  }, []);

  if (!process.env.BACKEND_URL || process.env.BACKEND_URL == "")
    return <BackendURL />;

  if (loadingSession) return null;

  return (
    <BrowserRouter basename={basename}>
      <ScrollToTop>
        <Routes>
          <Route
            path="/admin/clients"
            element={
              <ProtectedRoute>
                <AdminShell>
                  <Clients />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Dashboard />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/teams"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Teams />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/teams/:team_id"
            element={
              <ProtectedRoute>
                <AppShell>
                  <TeamDetail />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/players"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Players />
                </AppShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/set-password"
            element={
              <ProtectedRoute allowFirstLogin={true}>
                <SetPassword />
              </ProtectedRoute>
            }
          />
          <Route
            path="/onboarding"
            element={
              <OnboardingRoute>
                <Onboarding />
              </OnboardingRoute>
            }
          />
          <Route path="/" element={<RoleRedirect />} />
          <Route path="*" element={<h1>Not found!</h1>} />
        </Routes>
      </ScrollToTop>
    </BrowserRouter>
  );
};

export default injectContext(Layout);
