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
      dashboardData: null,
      dashboardStats: null,
      nextMatch: null,

      adminClients: [],
      clubUsers: [],
      categories: [],
      teams: [],
      players: [],
      payments: [],
      paymentSummary: null,
      playerPayments: [],
      trainings: [],
      matches: [],
      clubMatches: [],
      matchTeam: null,
      tournaments: [],
      currentTournament: null,
      tournamentTeams: [],
      tournamentPlayers: [],
      registrationChargesPreview: null,
      refereeChargesPreview: null,
      teamTournamentEntries: [],
    },

    actions: {
      logoutLocal: () => {
        localStorage.removeItem("token");
        localStorage.removeItem("refresh");
        localStorage.removeItem("user");

        setStore({
          token: null,
          user: null,
          onboardingStatus: null,
          onboardingStep: null,
          club: null,
          dashboardData: null,
          dashboardStats: null,
          nextMatch: null,
          clubUsers: [],
        });
      },

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
            dashboardData: null,
            dashboardStats: null,
            nextMatch: null,
            clubUsers: [],
          });

          localStorage.setItem("token", data.token);
          localStorage.setItem("refresh", data.refresh);
          localStorage.setItem("user", JSON.stringify(data.user));

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error login:", error);
        }
      },

      requestPasswordReset: async (email) => {
        try {
          const resp = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ email }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error requesting password reset:", error);
        }
      },

      resetPassword: async (token, newPassword) => {
        try {
          const resp = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              token,
              new_password: newPassword,
            }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error resetting password:", error);
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
          dashboardData: null,
          dashboardStats: null,
          nextMatch: null,
          clubUsers: [],
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

          const data = result.data;
          const store = getStore();
          const updatedUser = data.user || {
            ...store.user,
            first_login: false,
          };

          localStorage.setItem("token", data.token);
          localStorage.setItem("refresh", data.refresh);
          localStorage.setItem("user", JSON.stringify(updatedUser));

          setStore({
            user: updatedUser,
            token: data.token,
          });

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

      getCategories: async () => {
        try {
          const resp = await authFetch("/api/categories");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            categories: result.data.categories,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading categories:", error);
        }
      },

      getCategoryDetail: async (categoryId) => {
        try {
          const resp = await authFetch(`/api/categories/${categoryId}`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading category detail:", error);
        }
      },

      createCategory: async (categoryData) => {
        try {
          const resp = await authFetch("/api/categories", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(categoryData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getCategories();
          await actions.getOnboardingStatus();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating category:", error);
        }
      },

      updateCategory: async (categoryId, categoryData) => {
        try {
          const resp = await authFetch(`/api/categories/${categoryId}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(categoryData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getCategories();
          await actions.getOnboardingStatus();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating category:", error);
        }
      },

      createTeamInCategory: async (categoryId, teamData) => {
        try {
          const resp = await authFetch(`/api/categories/${categoryId}/teams`, {
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
          return networkError("Error creating team in category:", error);
        }
      },

      updateTeam: async (teamId, teamData) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}`, {
            method: "PUT",
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
          return networkError("Error updating team:", error);
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
            }
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

      getAdminSports: async () => {
        try {
          const resp = await authFetch("/api/admin/sports");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading sports:", error);
        }
      },

      getAdminCurrencies: async () => {
        try {
          const resp = await authFetch("/api/admin/currencies");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading currencies:", error);
        }
      },

      getAdminCountries: async () => {
        try {
          const resp = await authFetch("/api/admin/countries");
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading countries:", error);
        }
      },

      getAdminAreas: async (countryId) => {
        try {
          const resp = await authFetch(
            `/api/admin/countries/${countryId}/areas`,
          );
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading administrative areas:", error);
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

      suspendClub: async (clubId) => {
        try {
          const resp = await authFetch(`/api/admin/clubs/${clubId}/suspend`, {
            method: "PUT",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getAdminClients();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error suspending club:", error);
        }
      },

      activateClub: async (clubId) => {
        try {
          const resp = await authFetch(`/api/admin/clubs/${clubId}/activate`, {
            method: "PUT",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getAdminClients();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error activating club:", error);
        }
      },

      getClubUsers: async () => {
        try {
          const resp = await authFetch("/api/club/users");
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            clubUsers: result.data.users,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading club users:", error);
        }
      },

      createClubUser: async (userData) => {
        try {
          const resp = await authFetch("/api/club/users", {
            method: "POST",
            body: JSON.stringify(userData),
          });
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getClubUsers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating club user:", error);
        }
      },

      updateClubUser: async (userId, userData) => {
        try {
          const resp = await authFetch(`/api/club/users/${userId}`, {
            method: "PUT",
            body: JSON.stringify(userData),
          });
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getClubUsers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating club user:", error);
        }
      },

      deactivateClubUser: async (userId) => {
        try {
          const resp = await authFetch(`/api/club/users/${userId}/deactivate`, {
            method: "PUT",
          });
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getClubUsers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error deactivating club user:", error);
        }
      },

      activateClubUser: async (userId) => {
        try {
          const resp = await authFetch(`/api/club/users/${userId}/activate`, {
            method: "PUT",
          });
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getClubUsers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error activating club user:", error);
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

      updatePlayerStatus: async (playerId, teamId, status) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/status`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              team_id: teamId,
              status,
            }),
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

      updatePlayerActiveStatus: async (playerId, isActive) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/active`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              is_active: isActive,
            }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getPlayers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating player active status:", error);
        }
      },

      deletePlayer: async (playerId) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}`, {
            method: "DELETE",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          await getActions().getPlayers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error deleting player:", error);
        }
      },

      getDashboard: async () => {
        try {
          setStore({ dashboardData: null });

          const resp = await authFetch("/api/club/dashboard");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const data = result.data;

          setStore({
            club: data.club,
            dashboardData: data,
            dashboardStats: data.stats,
            nextMatch: data.next_match,
          });

          return successResponse(data);
        } catch (error) {
          return networkError("Error loading dashboard:", error);
        }
      },

      updateClub: async (clubData) => {
        try {
          const resp = await authFetch("/api/club", {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(clubData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getOnboardingStatus();
          await actions.getDashboard();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating club:", error);
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
            }
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

      getTrainingDetail: async (trainingId) => {
        try {
          const resp = await authFetch(`/api/trainings/${trainingId}`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading training detail:", error);
        }
      },

      updateTraining: async (trainingId, trainingData) => {
        try {
          const resp = await authFetch(`/api/trainings/${trainingId}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(trainingData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating training:", error);
        }
      },

      correctTrainingMetadata: async (trainingId, reason, changes) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/corrections/metadata`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ reason, changes }),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error correcting training metadata:", error);
        }
      },

      reactivateTraining: async (trainingId, reason) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/reactivate`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ reason }),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error reactivating training:", error);
        }
      },

      getTrainingAudit: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/audit`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data.audit_events);
        } catch (error) {
          return networkError("Error loading training audit:", error);
        }
      },

      completeTraining: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/complete`,
            { method: "PUT" }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const store = getStore();

          setStore({
            trainings: store.trainings.map((training) =>
              training.id === trainingId
                ? { ...training, ...result.data.training }
                : training
            ),
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error completing training:", error);
        }
      },

      cancelTraining: async (trainingId) => {
        try {
          const resp = await authFetch(`/api/trainings/${trainingId}/cancel`, {
            method: "PUT",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const store = getStore();

          setStore({
            trainings: store.trainings.map((training) =>
              training.id === trainingId
                ? { ...training, ...result.data.training }
                : training
            ),
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error cancelling training:", error);
        }
      },

      syncTrainingRoster: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/sync-roster`,
            { method: "PUT" }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const playersResult = await getActions().getTrainingPlayers(
            trainingId
          );

          if (!playersResult.ok) return playersResult;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error syncing training roster:", error);
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
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving attendance:", error);
        }
      },

      correctTrainingAttendance: async (
        trainingId,
        reason,
        attendanceList
      ) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/corrections/attendance`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                reason,
                attendance: attendanceList,
              }),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error correcting training attendance:", error);
        }
      },

      getTrainingAttendance: async (trainingId) => {
        try {
          const resp = await authFetch(
            `/api/trainings/${trainingId}/attendance`
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

      getPlayerPerformance: async (playerId) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/performance`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading player performance:", error);
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
      getTournaments: async (filters = {}) => {
        try {
          const params = new URLSearchParams();

          if (filters.status) {
            params.append("status", filters.status);
          }

          const queryString = params.toString();

          const endpoint = queryString
            ? `/api/tournaments?${queryString}`
            : "/api/tournaments";

          const resp = await authFetch(endpoint);
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            tournaments: result.data.tournaments || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading tournaments:", error);
        }
      },

      createTournament: async (tournamentData) => {
        try {
          const resp = await authFetch("/api/tournaments", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(tournamentData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getTournaments();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating tournament:", error);
        }
      },

      getTournamentDetail: async (tournamentId) => {
        try {
          const resp = await authFetch(`/api/tournaments/${tournamentId}`);
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            currentTournament: result.data.tournament || null,
            tournamentTeams: result.data.tournament?.teams || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading tournament detail:", error);
        }
      },

      updateTournament: async (tournamentId, tournamentData) => {
        try {
          const resp = await authFetch(`/api/tournaments/${tournamentId}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(tournamentData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getTournamentDetail(tournamentId);
          await actions.getTournaments();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating tournament:", error);
        }
      },

      completeTournament: async (tournamentId) => {
        try {
          const resp = await authFetch(
            `/api/tournaments/${tournamentId}/complete`,
            {
              method: "PUT",
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getTournaments();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error completing tournament:", error);
        }
      },

      cancelTournament: async (tournamentId) => {
        try {
          const resp = await authFetch(
            `/api/tournaments/${tournamentId}/cancel`,
            {
              method: "PUT",
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getTournaments();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error cancelling tournament:", error);
        }
      },

      addTeamToTournament: async (tournamentId, teamData) => {
        try {
          const resp = await authFetch(
            `/api/tournaments/${tournamentId}/teams`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(teamData),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getTournamentDetail(tournamentId);

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error adding team to tournament:", error);
        }
      },

      getTournamentTeams: async (tournamentId) => {
        try {
          const resp = await authFetch(
            `/api/tournaments/${tournamentId}/teams`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            tournamentTeams: result.data.teams || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading tournament teams:", error);
        }
      },

      getTournamentTeamPlayers: async (tournamentTeamId) => {
        try {
          const resp = await authFetch(
            `/api/tournament-teams/${tournamentTeamId}/players`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            tournamentPlayers: result.data.players || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading tournament players:", error);
        }
      },

      updateTournamentTeamPlayers: async (tournamentTeamId, playerIds) => {
        try {
          const resp = await authFetch(
            `/api/tournament-teams/${tournamentTeamId}/players`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                player_ids: playerIds,
              }),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getTournamentTeamPlayers(tournamentTeamId);

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating tournament players:", error);
        }
      },

      previewRegistrationCharges: async (tournamentTeamId) => {
        try {
          const resp = await authFetch(
            `/api/tournament-teams/${tournamentTeamId}/registration-charges/preview`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            registrationChargesPreview: result.data,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError(
            "Error loading registration charges preview:",
            error
          );
        }
      },

      getTournamentRegistrationChargeContexts: async () => {
        try {
          const resp = await authFetch("/api/tournament-registration-charges");
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError(
            "Error loading tournament registration charge contexts:",
            error
          );
        }
      },

      generateRegistrationCharges: async (tournamentTeamId) => {
        try {
          const resp = await authFetch(
            `/api/tournament-teams/${tournamentTeamId}/registration-charges`,
            {
              method: "POST",
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.previewRegistrationCharges(tournamentTeamId);

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error generating registration charges:", error);
        }
      },

      getTeamTournamentEntries: async (teamId) => {
        try {
          const resp = await authFetch(
            `/api/teams/${teamId}/tournament-entries`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            teamTournamentEntries: result.data.tournament_entries || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading team tournament entries:", error);
        }
      },

      clearRegistrationChargesPreview: () => {
        setStore({
          registrationChargesPreview: null,
        });
      },
      getClubMatches: async () => {
        try {
          const resp = await authFetch("/api/matches");

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            clubMatches: result.data.matches || [],
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading club matches:", error);
        }
      },

      getTeamMatches: async (teamId) => {
        try {
          const resp = await authFetch(`/api/teams/${teamId}/matches`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            matches: result.data.matches || [],
            matchTeam: result.data.team || null,
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

      updateMatchCaptureMode: async (matchId, captureMode) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}/capture-mode`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ capture_mode: captureMode }),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating match capture mode:", error);
        }
      },

      previewRefereeCharges: async (matchId) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/referee-charges/preview`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            refereeChargesPreview: result.data,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading referee charges preview:", error);
        }
      },

      generateRefereeCharges: async (matchId) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/referee-charges`,
            {
              method: "POST",
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.previewRefereeCharges(matchId);

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error generating referee charges:", error);
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
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving match status:", error);
        }
      },

      saveStartingLineup: async (matchId, players) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/starting-lineup`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                players,
              }),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving starting lineup:", error);
        }
      },

      createMatchSubstitution: async (matchId, substitutionData) => {
        try {
          const resp = await authFetch(
            `/api/matches/${matchId}/substitutions`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(substitutionData),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating substitution:", error);
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
            }
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
            }
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
            `/api/match-players/${matchPlayerId}/stats`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
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

      saveMatchResult: async (matchId, resultData) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}/result`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(resultData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error saving match result:", error);
        }
      },
      finalizeMatch: async (matchId) => {
        try {
          const resp = await authFetch(`/api/matches/${matchId}/finalize`, {
            method: "PUT",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error finalizing match:", error);
        }
      },
      createMatchEvent: async (eventData) => {
        try {
          const resp = await authFetch("/api/match-events", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(eventData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating match event:", error);
        }
      },
      deleteMatchEvent: async (eventId) => {
        try {
          const resp = await authFetch(`/api/match-events/${eventId}`, {
            method: "DELETE",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error deleting match event:", error);
        }
      },

      uploadClubImage: async (file) => {
        try {
          const formData = new FormData();
          formData.append("image", file);

          const resp = await authFetch("/api/club/upload-image", {
            method: "POST",
            body: formData,
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error uploading club image:", error);
        }
      },
      uploadPlayerImage: async (playerId, file) => {
        try {
          const formData = new FormData();
          formData.append("image", file);

          const resp = await authFetch(
            `/api/players/${playerId}/upload-image`,
            {
              method: "POST",
              body: formData,
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();
          await actions.getPlayers();

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error uploading player image:", error);
        }
      },

      getPayments: async (filters = {}) => {
        try {
          const params = new URLSearchParams();

          if (filters.status) {
            params.append("status", filters.status);
          }

          if (filters.payment_type) {
            params.append("payment_type", filters.payment_type);
          }

          const queryString = params.toString();
          const endpoint = queryString
            ? `/api/payments?${queryString}`
            : "/api/payments";

          const resp = await authFetch(endpoint);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            payments: result.data.payments,
            paymentSummary: result.data.summary,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading payments:", error);
        }
      },

      getPaymentsSyncPreview: async () => {
        try {
          const resp = await authFetch("/api/payments/sync-preview");
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading payments sync preview:", error);
        }
      },

      syncPayments: async () => {
        try {
          const resp = await authFetch("/api/payments/sync", {
            method: "POST",
          });
          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error syncing payments:", error);
        }
      },

      updatePayment: async (paymentId, paymentData, refreshFilters = null) => {
        try {
          const resp = await authFetch(`/api/payments/${paymentId}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(paymentData),
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const store = getStore();

          const updatedPayments = store.payments.map((payment) =>
            payment.id === paymentId ? result.data.payment : payment
          );

          setStore({
            payments: updatedPayments,
          });

          if (refreshFilters) {
            const actions = getActions();
            await actions.getPayments(refreshFilters);
          }

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating payment:", error);
        }
      },

      createPaymentReceipt: async (paymentId) => {
        try {
          const resp = await authFetch(`/api/payments/${paymentId}/receipt`, {
            method: "POST",
          });

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error creating payment receipt:", error);
        }
      },

      createPaymentReceiptShareEvent: async (receiptId, shareData) => {
        try {
          const resp = await authFetch(
            `/api/payment-receipts/${receiptId}/share-events`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(shareData),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error recording receipt share event:", error);
        }
      },

      getPaymentReceiptShareEvents: async (receiptId) => {
        try {
          const resp = await authFetch(
            `/api/payment-receipts/${receiptId}/share-events`
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading receipt share history:", error);
        }
      },

      getPlayerPayments: async (playerId) => {
        try {
          const resp = await authFetch(`/api/players/${playerId}/payments`);

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          setStore({
            playerPayments: result.data.payments,
          });

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error loading player payments:", error);
        }
      },

      updatePlayerPaymentSettings: async (playerId, paymentSettings) => {
        try {
          const resp = await authFetch(
            `/api/players/${playerId}/payment-settings`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(paymentSettings),
            }
          );

          const result = await parseResponse(resp);

          if (!result.ok) return result;

          const actions = getActions();

          await actions.getPlayers();
          await actions.getPlayerPayments(playerId);

          return successResponse(result.data);
        } catch (error) {
          return networkError("Error updating player payment settings:", error);
        }
      },
      restoreSession: async () => {
        const refresh = localStorage.getItem("refresh");

        if (!refresh) {
          setStore({ user: null, token: null, clubUsers: [] });

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

          setStore({ user: null, token: null, clubUsers: [] });

          return networkError("Error restoring session:", err);
        }
      },
    },
  };

  return state;
};

export default getState;
