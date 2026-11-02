import React, { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Context } from "../../store/appContext";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { errorMessages } from "../../utils/errorMessages";

const STALE_ASSIGNMENT_ERRORS = [
  "COACH_NOT_FOUND",
  "USER_NOT_COACH",
  "COACH_INACTIVE",
  "COACH_ASSIGNMENT_CONFLICT",
];
const STALE_TEAM_ERRORS = ["TEAM_ARCHIVED", "SEASON_CLOSED"];

const getCoachStatus = (coach, canOperateTeam) => {
  if (coach.role !== "coach") {
    return {
      label: "Otro rol",
      className: "status-muted",
      detail: "Ya no tiene rol de entrenador.",
    };
  }

  if (!coach.is_active) {
    return {
      label: "Inactivo",
      className: "status-muted",
      detail: "Su cuenta está desactivada.",
    };
  }

  return {
    label: "Activo",
    className: "status-success",
    detail: canOperateTeam
      ? "Puede operar este equipo."
      : "Asignado al equipo.",
  };
};

const getLifecycleNotice = (team) => {
  if (team.status === "archived") {
    return "Este equipo está archivado: no admite nuevas asignaciones.";
  }

  if (team.season_status === "closed") {
    return "Este equipo pertenece a una temporada cerrada: no admite nuevas asignaciones.";
  }

  if (team.season_status === "planned") {
    return "Este equipo pertenece a una temporada planificada. Puedes preparar sus entrenadores; podrán operarlo cuando la temporada se active.";
  }

  return null;
};

const getRemovalMessage = (coach, team, usesTeamScope) => {
  const isHistorical =
    team.status === "archived" || team.season_status === "closed";

  const effect = isHistorical
    ? "Dejará de figurar como asignado a este equipo."
    : usesTeamScope
    ? "Dejará de poder operar este equipo."
    : "Dejará de figurar como asignado a este equipo. Si el club usa permisos por equipos, tampoco podrá operarlo.";

  return `¿Retirar a ${coach.full_name} de este equipo?\n\n${effect} Su usuario no se elimina y el historial se conserva.`;
};

export const TeamCoachesSection = ({ team, onTeamChanged, onCoachesChange }) => {
  const { store, actions } = useContext(Context);

  const [coaches, setCoaches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [usersFailed, setUsersFailed] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [selectedCoachId, setSelectedCoachId] = useState("");
  const [saving, setSaving] = useState(false);
  const [removingCoachId, setRemovingCoachId] = useState(null);
  const [errorCode, setErrorCode] = useState(null);

  const club = store.club || store.user?.club;
  const usesTeamScope = club?.coach_access_mode === "team_assigned";
  const canAssign =
    team.status === "active" &&
    ["active", "planned"].includes(team.season_status);
  // Una asignación solo da operación en team_assigned y con el equipo operativo.
  const canOperateTeam =
    usesTeamScope &&
    team.status === "active" &&
    team.season_status === "active";
  const assignedCoachIds = coaches.map((coach) => coach.user_id);
  const candidates = (store.clubUsers || [])
    .filter(
      (user) =>
        user.role === "coach" &&
        user.is_active &&
        !assignedCoachIds.includes(user.id),
    )
    .sort((first, second) => first.full_name.localeCompare(second.full_name));
  const lifecycleNotice = getLifecycleNotice(team);

  const loadCoaches = async () => {
    const [coachesResult, usersResult] = await Promise.all([
      actions.getTeamCoaches(team.id),
      actions.getClubUsers(),
    ]);

    setUsersFailed(!usersResult.ok);

    if (!coachesResult.ok) {
      setLoadFailed(true);
      return;
    }

    setLoadFailed(false);
    setCoaches(coachesResult.data.coaches || []);
  };

  const handleRetry = async () => {
    setLoading(true);
    await loadCoaches();
    setLoading(false);
  };

  useEffect(() => {
    handleRetry();
  }, [team.id]);

  useEffect(() => {
    if (!canAssign) setShowForm(false);
  }, [canAssign]);

  useEffect(() => {
    onCoachesChange(coaches.length);
  }, [coaches.length]);

  const closeForm = () => {
    setShowForm(false);
    setSelectedCoachId("");
    setErrorCode(null);
  };

  const handleAssign = async (event) => {
    event.preventDefault();

    if (saving) return;

    if (!selectedCoachId) {
      setErrorCode("COACH_ID_REQUIRED");
      return;
    }

    setSaving(true);
    setErrorCode(null);

    const result = await actions.assignTeamCoach(team.id, selectedCoachId);

    if (!result.ok) {
      setErrorCode(result.code || "NETWORK_ERROR");
      setSelectedCoachId("");

      if (STALE_ASSIGNMENT_ERRORS.includes(result.code)) {
        await loadCoaches();
      }

      if (STALE_TEAM_ERRORS.includes(result.code)) {
        await onTeamChanged();
        await loadCoaches();
      }

      setSaving(false);
      return;
    }

    await loadCoaches();
    closeForm();
    setSaving(false);
  };

  const handleRemove = async (coach) => {
    if (removingCoachId) return;

    const confirmed = window.confirm(
      getRemovalMessage(coach, team, usesTeamScope),
    );

    if (!confirmed) return;

    setRemovingCoachId(coach.user_id);
    setErrorCode(null);

    const result = await actions.removeTeamCoach(team.id, coach.user_id);

    if (!result.ok) {
      setErrorCode(result.code || "NETWORK_ERROR");
    }

    await loadCoaches();
    setRemovingCoachId(null);
  };

  const errorMessage =
    errorCode &&
    (errorMessages[errorCode] || "No se pudo actualizar los entrenadores");

  return (
    <Card className="team-coaches-card">
      <div className="team-coaches-header">
        <h4>Cuerpo técnico</h4>

        {canAssign &&
          !loading &&
          !loadFailed &&
          !showForm &&
          candidates.length > 0 && (
            <Button
              variant="secondary"
              onClick={() => {
                setErrorCode(null);
                setShowForm(true);
              }}
            >
              Asignar entrenador
            </Button>
          )}
      </div>

      {lifecycleNotice && (
        <p className="team-coaches-notice">{lifecycleNotice}</p>
      )}

      {loading ? (
        <p className="team-coaches-muted" role="status">
          Cargando entrenadores...
        </p>
      ) : loadFailed ? (
        <div className="team-coaches-error" role="alert">
          <p className="form-error">
            No se pudieron cargar los entrenadores de este equipo.
          </p>
          <Button variant="secondary" onClick={handleRetry}>
            Volver a intentar
          </Button>
        </div>
      ) : (
        <>
          {errorMessage && <p className="form-error">{errorMessage}</p>}

          {showForm && candidates.length > 0 && (
            <form className="team-coaches-form" onSubmit={handleAssign}>
              <FormField label="Entrenador">
                <Select
                  value={selectedCoachId}
                  disabled={saving}
                  onChange={(event) => {
                    setSelectedCoachId(event.target.value);
                    setErrorCode(null);
                  }}
                >
                  <option value="">Selecciona un entrenador</option>

                  {candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.full_name}
                    </option>
                  ))}
                </Select>
              </FormField>

              <div className="form-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeForm}
                  disabled={saving}
                >
                  Cancelar
                </Button>

                <Button type="submit" disabled={saving}>
                  {saving ? "Asignando..." : "Asignar"}
                </Button>
              </div>
            </form>
          )}

          {coaches.length === 0 ? (
            <p className="team-coaches-muted">
              Aún no hay entrenadores asignados.
            </p>
          ) : (
            <div className="team-coaches-list">
              {coaches.map((coach) => {
                const status = getCoachStatus(coach, canOperateTeam);

                return (
                  <div className="team-coach-row" key={coach.assignment_id}>
                    <div className="team-coach-info">
                      <strong>{coach.full_name}</strong>
                      <span>{status.detail}</span>
                    </div>

                    <div className="team-coach-actions">
                      <span className={`status-badge ${status.className}`}>
                        {status.label}
                      </span>

                      <Button
                        type="button"
                        variant="secondary"
                        aria-label={`Retirar a ${coach.full_name} de este equipo`}
                        disabled={removingCoachId !== null}
                        onClick={() => handleRemove(coach)}
                      >
                        {removingCoachId === coach.user_id
                          ? "Retirando..."
                          : "Retirar"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {canAssign && usersFailed && (
            <p className="form-error">
              No se pudo cargar la lista de entrenadores disponibles.
            </p>
          )}

          {canAssign && !usersFailed && candidates.length === 0 && (
            <p className="team-coaches-muted">
              No hay más entrenadores activos disponibles. Puedes crearlos en{" "}
              <Link to="/club/users">Usuarios</Link>.
            </p>
          )}
        </>
      )}
    </Card>
  );
};
