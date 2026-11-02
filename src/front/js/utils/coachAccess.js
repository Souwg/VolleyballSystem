import { useEffect, useRef } from "react";

export const TEAM_ACCESS_LOST_EVENT = "sportflow:team-access-lost";

export const isScopedCoach = (store) => {
  const club = store.club || store.user?.club;

  return (
    store.user?.role === "coach" &&
    club?.coach_access_mode === "team_assigned"
  );
};

// can_manage es permiso por asignación, no lifecycle: combínalo con
// isTeamOperational. Sin metadata no se bloquea: decide el backend.
export const canManage = (resource) => resource?.can_manage !== false;

export const isTeamOperational = (team) =>
  !team ||
  (team.status === "active" &&
    (team.season_status === undefined || team.season_status === "active"));

export const getManageableTeams = (teams) => (teams || []).filter(canManage);

// El backend omite los campos que este usuario no puede ver: ausente no es vacío.
export const hasField = (resource, field) =>
  Boolean(resource) && Object.prototype.hasOwnProperty.call(resource, field);

export const resolveTeamOperational = async (actions, teamId) => {
  if (!teamId) return true;

  const result = await actions.getTeamDetail(teamId);

  return result.ok ? isTeamOperational(result.data.team) : true;
};

export const useTeamAccessLost = (onLost) => {
  const callback = useRef(onLost);

  callback.current = onLost;

  useEffect(() => {
    const handleLost = () => callback.current?.();

    window.addEventListener(TEAM_ACCESS_LOST_EVENT, handleLost);

    return () => window.removeEventListener(TEAM_ACCESS_LOST_EVENT, handleLost);
  }, []);
};
