import React, { useEffect, useState, useContext } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Context } from "./store/appContext";

import ScrollToTop from "./component/scrollToTop";
import { RoleRedirect } from "./component/roleRedirect";
import { BackendURL } from "./component/backendURL";
import { PublicRoute } from "./component/publicRoute";
import { ProtectedRoute } from "./component/protectedRoute";
import { OnboardingRoute } from "./component/onboardingRoute";
import { SplashScreen } from "./component/splashScreen";

import { Clients } from "./pages/admin/clients";
import { Login } from "./pages/auth/login";
import { ForgotPassword } from "./pages/auth/forgotPassword";
import { ResetPassword } from "./pages/auth/resetPassword";
import { AppShell } from "./component/appShell";
import { AdminShell } from "./component/adminShell";
import { Dashboard } from "./pages/dashboard/dashboard";
import { SetPassword } from "./pages/auth/setPassword";
import { Onboarding } from "./pages/onboarding/onboarding";
import { Categories } from "./pages/categories/categories";
import { CategoryDetail } from "./pages/categories/categoryDetail";
import { TeamDetail } from "./pages/teams/teamDetail";
import { Players } from "./pages/players/players";
import { PlayerDetail } from "./pages/players/playerDetail";
import { EditPlayer } from "./pages/players/editPlayer";
import { PlayerPayments } from "./pages/players/playerPayments";
import { Trainings } from "./pages/trainings/trainings";
import { TeamTrainings } from "./pages/trainings/teamTrainings";
import { TrainingDetail } from "./pages/trainings/trainingDetail";
import { CreateTraining } from "./pages/trainings/createTraining";
import { Tournaments } from "./pages/tournaments/tournaments";
import { TournamentDetail } from "./pages/tournaments/tournamentDetail";
import { TournamentTeamDetail } from "./pages/tournaments/tournamentTeamDetail";
import { MatchSessions } from "./pages/matches/matchSessions";
import { Matches } from "./pages/matches/matches";
import { CreateMatch } from "./pages/matches/createMatch";
import { MatchDetail } from "./pages/matches/matchDetail";
import { LiveMatch } from "./pages/matches/LiveMatch";
import { PlayerMatchStats } from "./pages/matches/playerMatchStats";
import { MatchStatsAdjust } from "./pages/matches/matchStatsAdjust";
import { ClubProfile } from "./pages/club/clubProfile";
import { Payments } from "./pages/payments/payments";
import injectContext from "./store/appContext";

const Layout = () => {
  const basename = process.env.BASENAME || "";

  const { actions } = useContext(Context);

  const [loadingSession, setLoadingSession] = useState(true);

  const [showSplash, setShowSplash] = useState(() => {
    return sessionStorage.getItem("sportflow_splash_seen") !== "true";
  });

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

  useEffect(() => {
    if (!showSplash) return;

    const splashTimer = window.setTimeout(() => {
      sessionStorage.setItem("sportflow_splash_seen", "true");
      setShowSplash(false);
    }, 2500);

    return () => {
      window.clearTimeout(splashTimer);
    };
  }, [showSplash]);

  if (!process.env.BACKEND_URL || process.env.BACKEND_URL == "") {
    return <BackendURL />;
  }

  if (showSplash || loadingSession) {
    return <SplashScreen />;
  }

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
          <Route
            path="/forgot-password"
            element={
              <PublicRoute>
                <ForgotPassword />
              </PublicRoute>
            }
          />

          <Route
            path="/reset-password"
            element={
              <PublicRoute>
                <ResetPassword />
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
              <Route path="/club/profile" element={<ClubProfile />} />
              <Route path="/payments" element={<Payments />} />
              <Route path="/categories" element={<Categories />} />
              <Route
                path="/categories/:category_id"
                element={<CategoryDetail />}
              />
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
              <Route path="/matches" element={<Matches />} />
              <Route path="/tournaments" element={<Tournaments />} />
              <Route
                path="/tournaments/:tournament_id"
                element={<TournamentDetail />}
              />
              <Route
                path="/tournament-teams/:tournament_team_id"
                element={<TournamentTeamDetail />}
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
              <Route
                path="/players/:player_id/payments"
                element={<PlayerPayments />}
              />
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
