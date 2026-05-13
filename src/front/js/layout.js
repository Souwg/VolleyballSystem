import React, { useEffect, useState, useContext } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Context } from "./store/appContext";

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
import { PlayerDetail } from "./pages/players/playerDetail";
import { EditPlayer } from "./pages/players/editPlayer";
import { Trainings } from "./pages/trainings/trainings";
import { TeamTrainings } from "./pages/trainings/teamTrainings";
import { TrainingDetail } from "./pages/trainings/trainingDetail";
import { CreateTraining } from "./pages/trainings/createTraining";
import { MatchSessions } from "./pages/matches/matchSessions";
import { CreateMatch } from "./pages/matches/createMatch";
import { MatchDetail } from "./pages/matches/matchDetail";
import { LiveMatch } from "./pages/matches/liveMatch";
import { PlayerMatchStats } from "./pages/matches/playerMatchStats";
import { MatchStatsAdjust } from "./pages/matches/matchStatsAdjust";
import injectContext from "./store/appContext";

const Layout = () => {
  const basename = process.env.BASENAME || "";

  const { actions } = useContext(Context);

  const [loadingSession, setLoadingSession] = useState(true);

  useEffect(() => {
    const initSession = async () => {
      try {
        const restored = await actions.restoreSession();

        if (restored?.ok) {
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
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />
          <Route element={<ProtectedRoute />}>
            <Route element={<AdminShell />}>
              <Route path="/admin/clients" element={<Clients />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/teams" element={<Teams />} />
              <Route path="/teams/:team_id" element={<TeamDetail />} />
              <Route path="/trainings" element={<Trainings />} />
              <Route
                path="/teams/:team_id/trainings"
                element={<TeamTrainings />}
              />
              <Route
                path="/trainings/:training_id"
                element={<TrainingDetail />}
              />
              <Route path="/trainings/new" element={<CreateTraining />} />
              <Route
                path="/teams/:team_id/trainings/new"
                element={<CreateTraining />}
              />
              <Route
                path="/teams/:team_id/matches"
                element={<MatchSessions />}
              />
              <Route
                path="/teams/:team_id/matches/new"
                element={<CreateMatch />}
              />

              <Route path="/matches/:match_id" element={<MatchDetail />} />
              <Route path="/matches/:match_id/live" element={<LiveMatch />} />
              <Route
                path="/matches/:match_id/stats"
                element={<MatchStatsAdjust />}
              />
              <Route
                path="/match-players/:match_player_id/stats"
                element={<PlayerMatchStats />}
              />
              <Route path="/players" element={<Players />} />
              <Route path="/players/:player_id/edit" element={<EditPlayer />} />
              <Route path="/players/:player_id" element={<PlayerDetail />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute allowFirstLogin={true} />}>
            <Route path="/set-password" element={<SetPassword />} />
          </Route>
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
