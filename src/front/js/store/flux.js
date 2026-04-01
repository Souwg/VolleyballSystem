import { authFetch, setAuthActions, parseResponse } from "../utils/authFetch";

const BACKEND_URL =
  process.env.REACT_APP_BACKEND_URL || "http://localhost:3001";

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

          return {
            ok: true,
            data: {
              first_login: data.first_login,
              user: data.user,
            },
          };
        } catch (error) {
          console.error("Error login:", error);

          return {
            success: false,
            message: "Error de conexión",
            code: "NETWORK_ERROR",
          };
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

          return {
            ok: true,
          };
        } catch (error) {
          console.error("Error setting password:", error);

          return {
            success: false,
            message: "Error de conexión",
          };
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

          return data;
        } catch (error) {
          console.error("Error loading onboarding status:", error);
        }
      },
      getTeams: async () => {
        try {
          const resp = await authFetch("/api/teams");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({ teams: result.data.teams });

          return result.data;
        } catch (error) {
          console.error("Error loading teams:", error);
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

          return result.data;
        } catch (error) {
          console.error("Error loading players:", error);
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

          return result.data;
        } catch (error) {
          console.error("Error loading clients:", error);
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

          return result;
        } catch (error) {
          console.error("Error creating client:", error);
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

          return result;
        } catch (error) {
          console.error("Error updating client status:", error);
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

          return result;
        } catch (error) {
          console.error("Error updating player:", error);
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

          return result.data;
        } catch (error) {
          console.error("Error loading team players:", error);
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

          return result;
        } catch (error) {
          console.error("Error updating player status:", error);
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

          return data;
        } catch (error) {
          console.error("Error loading dashboard:", error);
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

          return result;
        } catch (error) {
          console.error("Error updating club:", error);
        }
      },

      createTeam: async (teamName) => {
        try {
          const resp = await authFetch("/api/teams", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              name: teamName,
            }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getTeams();
          await actions.getOnboardingStatus();

          return result;
        } catch (error) {
          console.error("Error creating team:", error);
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

          return result;
        } catch (error) {
          console.error("Error deleting team:", error);
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

          return result;
        } catch (error) {
          console.error("Error creating player:", error);
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

          return result.data;
        } catch (error) {
          console.error("Error loading trainings:", error);
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

          return result;
        } catch (error) {
          console.error("Error creating training:", error);
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

          return result;
        } catch (error) {
          console.error("Error saving attendance:", error);
        }
      },

      getTrainingAttendance: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/attendance`,
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return result.data.attendance;
        } catch (error) {
          console.error("Error loading attendance:", error);
        }
      },
      getPlayerAttendance: async (playerId) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/attendance`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return result.data;
        } catch (err) {
          console.error(err);
          return {
            ok: false,
            message: "Error de conexión",
            code: "NETWORK_ERROR",
          };
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

          return result.data;
        } catch (error) {
          console.error("Error loading all trainings:", error);
        }
      },
      restoreSession: async () => {
        const refresh = localStorage.getItem("refresh");

        if (!refresh) {
          setStore({ user: null, token: null });
          return false;
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

          return true;
        } catch (err) {
          localStorage.removeItem("token");
          localStorage.removeItem("refresh");
          localStorage.removeItem("user");

          setStore({ user: null, token: null });

          return false;
        }
      },
    },
  };

  return state;
};

export default getState;
