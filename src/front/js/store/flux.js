import { authFetch, parseResponse } from "../utils/authFetch";

const BACKEND_URL =
  process.env.REACT_APP_BACKEND_URL || "http://localhost:3001";

const networkError = (label, error) => {
  console.error(label, error);

  return {
    ok: false,
    code: "NETWORK_ERROR",
    message: "Error de conexión",
  };
};

const successResponse = (data = null) => ({
  ok: true,
  data,
});

const getState = ({ getStore, getActions, setStore }) => {
  const state = {
    store: {
      message: null,
      user: null,
      token: null,
      onboardingStatus: null,
      onboardingStep: null,
      club: null,
      dashboardStats: null,

      adminClients: [],
      teams: [],
      players: [],
      trainings: [],
      matches: [],
    },

    actions: {
      loginUser: async (email, password) => {
        try {
          const resp = await fetch(`${BACKEND_URL}/api/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const data = result.data;

          setStore({
            user: data.user,
            token: data.token,
            firstLogin: data.first_login,
          });

          localStorage.setItem("token", data.token);
          localStorage.setItem("refresh", data.refresh);
          localStorage.setItem("user", JSON.stringify(data.user));

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error login:", error);
        }
      },

      logoutUser: async () => {
        try {
          const resp = await authFetch("/api/logout", {
            method: "POST",
          });

          const result = await parseResponse(resp);

          if (!result.ok) {
            console.warn("Logout failed:", result.message);
            // No bloqueamos el logout local aunque falle el backend
          }
        } catch (error) {
          console.error("Logout error:", error);
          // Igual seguimos con logout local
        }

        // 🔐 SIEMPRE limpiar local
        localStorage.removeItem("token");
        localStorage.removeItem("refresh");
        localStorage.removeItem("user");

        setStore({
          token: null,
          user: null,
          onboardingStatus: null,
        });
      },
      setPassword: async (newPassword) => {
        try {
          const resp = await authFetch("/api/auth/set-password", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              new_password: newPassword,
            }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const store = getStore();
          const updatedUser = { ...store.user, first_login: false };

          setStore({ user: updatedUser });
          localStorage.setItem("user", JSON.stringify(updatedUser));

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error setting password:", error);
        }
      },

      getOnboardingStatus: async () => {
        try {
          const resp = await authFetch("/api/onboarding/status");

          const result = await parseResponse(resp);

          if (!result.ok) {
            return result;
          }

          const data = result.data;

          setStore({
            onboardingStatus: data.status,
            onboardingStep: data.step,
            club: data.club,
          });

          return successResponse(data);
        } catch (error) {
          return networkError("Error loading onboarding status:", error);
        }
      },

      getTeams: async () => {
        try {
          const resp = await authFetch("/api/teams");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({ teams: result.data.teams });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading teams:", error);
        }
      },

      getPlayers: async () => {
        try {
          const resp = await authFetch("/api/players");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            players: result.data.players,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading players:", error);
        }
      },

      addExistingPlayerToTeam: async (teamId, playerData) => {
        try {
          const resp = await authFetch(
            `/api/teams/${teamId}/players/existing`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(playerData),
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error adding existing player:", error);
        }
      },

      getAdminClients: async () => {
        try {
          const resp = await authFetch("/api/admin/clients");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            adminClients: result.data.clients,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading clients:", error);
        }
      },

      createClient: async (clientData) => {
        try {
          const resp = await authFetch("/api/admin/create-client", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(clientData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getAdminClients();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating client:", error);
        }
      },

      toggleClientStatus: async (clientId, actionType) => {
        try {
          const endpoint =
            actionType === "deactivate"
              ? `/api/admin/clients/${clientId}/deactivate`
              : `/api/admin/clients/${clientId}/activate`;

          const resp = await authFetch(endpoint, {
            method: "PUT",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getAdminClients();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating client status:", error);
        }
      },

      updatePlayer: async (playerId, playerData) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(playerData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getPlayers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating player:", error);
        }
      },

      getTeamPlayers: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}/players`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            players: result.data.players,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading team players:", error);
        }
      },

      getTrainingPlayers: async (trainingId) => {
        try {
          const resp = await authFetch(`/api/trainings/${trainingId}/players`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            players: result.data.players,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading training snapshot:", error);
        }
      },

      updatePlayerStatus: async (playerId, status) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/status`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ status }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getPlayers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating player status:", error);
        }
      },

      getDashboard: async () => {
        try {
          const resp = await authFetch("/api/club/dashboard");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const data = result.data;

          setStore({
            club: data.club,
            dashboardStats: data.stats,
          });

          return successResponse(data);
        } catch (error) {
          return networkError("Error loading dashboard:", error);
        }
      },

      updateClub: async (location) => {
        try {
          const resp = await authFetch("/api/club", {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              location: location,
            }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getOnboardingStatus();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating club:", error);
        }
      },

      createTeam: async (teamData) => {
        try {
          const resp = await authFetch("/api/teams", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(teamData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getTeams();
          await actions.getOnboardingStatus();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating team:", error);
        }
      },

      deleteTeam: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}`, {
            method: "DELETE",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getTeams();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error deleting team:", error);
        }
      },

      createPlayer: async (playerData) => {
        try {
          const resp = await authFetch("/api/players", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(playerData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getPlayers();
          await actions.getOnboardingStatus();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating player:", error);
        }
      },

      removePlayerFromTeam: async (teamId, playerId) => {
        try {
          const resp = await authFetch(
            `/api/teams/${teamId}/players/${playerId}`,
            {
              method: "DELETE",
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error removing player from team:", error);
        }
      },

      getTeamTrainings: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}/trainings`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            trainings: result.data.trainings,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading trainings:", error);
        }
      },

      createTraining: async (trainingData) => {
        try {
          const resp = await authFetch("/api/trainings", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(trainingData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating training:", error);
        }
      },

      saveAttendance: async (trainingId, attendanceList) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/attendance`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                attendance: attendanceList,
              }),
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving attendance:", error);
        }
      },

      getTrainingAttendance: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/attendance`,
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data.attendance);
        } catch (error) {
          return networkError("Error loading attendance:", error);
        }
      },

      getPlayerAttendance: async (playerId) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/attendance`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (err) {
          return networkError("Error loading player attendance:", err);
        }
      },

      getAllTrainings: async () => {
        try {
          const resp = await authFetch("/api/trainings");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            trainings: result.data.trainings,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading all trainings:", error);
        }
      },

      getTeamMatches: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}/matches`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            matches: result.data.matches || result.data,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading matches:", error);
        }
      },

      createMatch: async (matchData) => {
        try {
          const resp = await authFetch("/api/matches", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(matchData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating match:", error);
        }
      },

      getMatchDetail: async (matchId) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading match detail:", error);
        }
      },

      saveMatchRoster: async (matchId, players) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}/roster`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ players }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving roster:", error);
        }
      },

      saveMatchStatus: async (matchId, players) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/roster/status`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ players }),
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving match status:", error);
        }
      },

      saveMatchParticipation: async (matchId, players) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/roster/participation`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ players }),
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving participation:", error);
        }
      },

      savePlayerMatchStats: async (matchPlayerId, statsData) => {
        try {
          const resp = await authFetch(
            `/api/match-players/${matchPlayerId}/stats`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(statsData),
            },
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving stats:", error);
        }
      },

      getPlayerMatchStats: async (matchPlayerId) => {
        try {
          const resp = await authFetch(
            `/api/match-players/${matchPlayerId}/stats`,
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data.stats || {});
        } catch (error) {
          return networkError("Error loading player stats:", error);
        }
      },

      getTeamPlayersOnly: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}/players`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data.players);
        } catch (error) {
          return networkError("Error loading team players:", error);
        }
      },

      getMatchRoster: async (matchId) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}/roster`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data.players);
        } catch (error) {
          return networkError("Error loading match roster:", error);
        }
      },

      restoreSession: async () => {
        const refresh = localStorage.getItem("refresh");

        if (!refresh) {
          setStore({ user: null, token: null });

          return {
            ok: false,
            code: "NO_REFRESH",
            message: "No hay sesión activa",
          };
        }

        try {
          const resp = await fetch(`${BACKEND_URL}/api/refresh`, {
            method: "POST",
            headers: { Authorization: `Bearer ${refresh}` },
          });

          const result = await parseResponse(resp);

          if (!result.ok) {
            throw new Error(result.code);
          }

          const data = result.data;

          localStorage.setItem("token", data.token);
          localStorage.setItem("refresh", data.refresh);

          const userRaw = localStorage.getItem("user");
          const user =
            userRaw && userRaw !== "undefined" ? JSON.parse(userRaw) : null;

          setStore({ user, token: data.token });

          return successResponse({
            restored: true,
            user,
            token: data.token,
          });
        } catch (err) {
          localStorage.removeItem("token");
          localStorage.removeItem("refresh");
          localStorage.removeItem("user");

          setStore({ user: null, token: null });

          return networkError("Error restoring session:", err);
        }
      },
    },
  };

  return state;
};

export default getState;
