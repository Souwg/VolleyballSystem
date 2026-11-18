import React, { useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { validateTraining } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { ReadOnlyNotice } from "../../component/ui/readOnlyNotice";
import {
  canManage,
  getManageableTeams,
  isScopedCoach,
  isTeamOperational,
} from "../../utils/coachAccess";
import "../../../styles/trainingShared.css";

export const CreateTraining = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const navigationLocation = useLocation();
  const { team_id } = useParams();

  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [location, setLocation] = useState("");
  const [selectedTeam, setSelectedTeam] = useState(team_id || "");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [teamsLoading, setTeamsLoading] = useState(true);
  const [teamLoadError, setTeamLoadError] = useState(null);
  const loadRequestId = useRef(0);

  const [fixedTeam, setFixedTeam] = useState(null);
  const manageableTeams = getManageableTeams(store.teams).filter(
    (team) => team.status === "active" && isTeamOperational(team),
  );
  const cannotCreate = !teamsLoading && (team_id
    ? !canManage(fixedTeam) || !isTeamOperational(fixedTeam)
    : isScopedCoach(store) && manageableTeams.length === 0);

  const loadTeams = async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setTeamsLoading(true);
    setTeamLoadError(null);
    setFixedTeam(null);
    setSelectedTeam(team_id || "");

    if (team_id) {
      const result = await actions.getTeamDetail(team_id);
      if (requestId !== loadRequestId.current) return;
      setFixedTeam(result.ok ? result.data.team : null);
      setTeamLoadError(result.ok ? null : result);
      setTeamsLoading(false);
      return;
    }

    const result = await actions.getTeams();
    if (requestId !== loadRequestId.current) return;
    setTeamLoadError(result.ok ? null : result);
    setTeamsLoading(false);
  };

  useEffect(() => {
    loadTeams();
    return () => {
      loadRequestId.current += 1;
    };
  }, [team_id]);

  const handleCreateTraining = async (e) => {
    e.preventDefault();

    if (loading) return;

    setErrors({});

    const newErrors = validateTraining({
      team_id: selectedTeam,
      date,
      start_time: startTime,
      end_time: endTime,
      location,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);

    const result = await actions.createTraining({
      team_id: selectedTeam,
      date: date.trim(),
      start_time: startTime.trim(),
      end_time: endTime.trim(),
      location: location.trim(),
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }

    setLoading(false);
    navigate(`/trainings/${result.data.training.id}`);
  };

  const generalErrorCode = Object.keys(errors).find(
    (code) => errors[code] && errorMessages[code],
  );
  const fixedContext = fixedTeam
    ? [
        fixedTeam.category?.name,
        fixedTeam.name,
        fixedTeam.season?.name,
      ].filter(Boolean).join(" · ")
    : null;

  return (
    <div className="training-form-page">
      <PageHeader
        variant="detail"
        eyebrow="Entrenamiento"
        title="Crear entrenamiento"
        subtitle="Registra una nueva sesión para una categoría."
        onBack={() =>
          navigate(
            navigationLocation.state?.from ||
            (team_id
              ? `/teams/${team_id}/trainings${navigationLocation.search}`
              : `/trainings${navigationLocation.search}`),
          )
        }
      />

      {teamsLoading ? (
        <p role="status">Cargando equipo...</p>
      ) : teamLoadError ? (
        <Card className="page-error-state" role="alert">
          <h2>No pudimos cargar el equipo</h2>
          <p>
            {errorMessages[teamLoadError.code] ||
              teamLoadError.message ||
              "Ocurrió un error temporal."}
          </p>
          <Button type="button" onClick={loadTeams}>Volver a intentar</Button>
        </Card>
      ) : cannotCreate ? (
        <ReadOnlyNotice>
          No puedes crear entrenamientos para este equipo en este momento.
        </ReadOnlyNotice>
      ) : (
      <Card>
        <h4>Detalles del entrenamiento</h4>
        {fixedContext && <p className="training-fixed-context">{fixedContext}</p>}
        <p>
          Se agregarán automáticamente los deportistas actualmente elegibles
          del equipo.
        </p>

        <form onSubmit={handleCreateTraining} className="form">
          {!team_id && (
            <FormField
              label="Categoría"
              htmlFor="training-team"
              errorId="training-team-error"
              error={
                errors.TEAM_ID_REQUIRED ? errorMessages.TEAM_ID_REQUIRED : null
              }
            >
              <Select
                id="training-team"
                aria-describedby={errors.TEAM_ID_REQUIRED ? "training-team-error" : undefined}
                className={errors.TEAM_ID_REQUIRED ? "input-error" : ""}
                value={selectedTeam}
                onChange={(e) => {
                  setSelectedTeam(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    TEAM_ID_REQUIRED: false,
                    TEAM_NOT_FOUND: false,
                    FORBIDDEN: false,
                    CLUB_REQUIRED: false,
                    SESSION_EXPIRED: false,
                    NETWORK_ERROR: false,
                  }));
                }}
              >
                <option value="">Selecciona una categoría</option>

                {manageableTeams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name} ·{" "}
                    {team.gender === "mixed"
                      ? "Mixto"
                      : team.gender === "male"
                      ? "Masculino"
                      : "Femenino"}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <FormField
            label="Fecha"
            htmlFor="training-date"
            errorId="training-date-error"
            error={
              errors.TRAINING_DATE_REQUIRED
                ? errorMessages.TRAINING_DATE_REQUIRED
                : null
            }
          >
            <Input
              id="training-date"
              aria-describedby={errors.TRAINING_DATE_REQUIRED ? "training-date-error" : undefined}
              type="date"
              value={date}
              className={errors.TRAINING_DATE_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setDate(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  TRAINING_DATE_REQUIRED: false,
                  TEAM_NOT_FOUND: false,
                  FORBIDDEN: false,
                  CLUB_REQUIRED: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                }));
              }}
            />
          </FormField>

          <div className="training-time-grid">
            <FormField
              label="Hora de inicio"
              htmlFor="training-start-time"
              errorId="training-start-time-error"
              error={
                errors.TRAINING_START_TIME_REQUIRED
                  ? errorMessages.TRAINING_START_TIME_REQUIRED
                  : null
              }
            >
              <Input
                id="training-start-time"
                aria-describedby={errors.TRAINING_START_TIME_REQUIRED ? "training-start-time-error" : undefined}
                type="time"
                value={startTime}
                className={
                  errors.TRAINING_START_TIME_REQUIRED ||
                  errors.INVALID_TRAINING_TIME_RANGE
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setStartTime(e.target.value);

                  setErrors((prev) => ({
                    ...prev,
                    TRAINING_START_TIME_REQUIRED: false,
                    INVALID_TIME_FORMAT: false,
                    INVALID_TRAINING_TIME_RANGE: false,
                    TEAM_NOT_FOUND: false,
                    FORBIDDEN: false,
                    CLUB_REQUIRED: false,
                    SESSION_EXPIRED: false,
                    NETWORK_ERROR: false,
                  }));
                }}
              />
            </FormField>

            <FormField
              label="Hora de finalización"
              htmlFor="training-end-time"
              errorId="training-end-time-error"
              error={
                errors.TRAINING_END_TIME_REQUIRED
                  ? errorMessages.TRAINING_END_TIME_REQUIRED
                  : errors.INVALID_TRAINING_TIME_RANGE
                  ? errorMessages.INVALID_TRAINING_TIME_RANGE
                  : null
              }
            >
              <Input
                id="training-end-time"
                aria-describedby={
                  errors.TRAINING_END_TIME_REQUIRED || errors.INVALID_TRAINING_TIME_RANGE
                    ? "training-end-time-error"
                    : undefined
                }
                type="time"
                value={endTime}
                className={
                  errors.TRAINING_END_TIME_REQUIRED ||
                  errors.INVALID_TRAINING_TIME_RANGE
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setEndTime(e.target.value);

                  setErrors((prev) => ({
                    ...prev,
                    TRAINING_END_TIME_REQUIRED: false,
                    INVALID_TIME_FORMAT: false,
                    INVALID_TRAINING_TIME_RANGE: false,
                    TEAM_NOT_FOUND: false,
                    FORBIDDEN: false,
                    CLUB_REQUIRED: false,
                    SESSION_EXPIRED: false,
                    NETWORK_ERROR: false,
                  }));
                }}
              />
            </FormField>
          </div>

          <FormField
            label="Ubicación"
            htmlFor="training-location"
            errorId="training-location-error"
            helper="Ej: Cancha central, Gimnasio municipal, Colegio..."
            error={
              errors.TRAINING_LOCATION_REQUIRED
                ? errorMessages.TRAINING_LOCATION_REQUIRED
                : null
            }
          >
            <Input
              id="training-location"
              aria-describedby={errors.TRAINING_LOCATION_REQUIRED ? "training-location-error" : undefined}
              type="text"
              placeholder="Ej: Cancha central"
              value={location}
              className={errors.TRAINING_LOCATION_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setLocation(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  TRAINING_LOCATION_REQUIRED: false,
                  TEAM_NOT_FOUND: false,
                  FORBIDDEN: false,
                  CLUB_REQUIRED: false,
                  SESSION_EXPIRED: false,
                  NETWORK_ERROR: false,
                }));
              }}
            />
          </FormField>
          {generalErrorCode && ![
            "TEAM_ID_REQUIRED",
            "TRAINING_DATE_REQUIRED",
            "TRAINING_START_TIME_REQUIRED",
            "TRAINING_END_TIME_REQUIRED",
            "INVALID_TRAINING_TIME_RANGE",
            "TRAINING_LOCATION_REQUIRED",
          ].includes(generalErrorCode) && (
            <div className="training-form-error" role="alert">
              <p className="form-error">{errorMessages[generalErrorCode]}</p>
              {generalErrorCode === "TEAM_HAS_NO_PLAYERS" && selectedTeam && (
                <Link to={`/teams/${selectedTeam}`}>Ver equipo</Link>
              )}
            </div>
          )}

          <div className="form-actions">
            <Button type="submit" disabled={loading}>
              {loading ? "Creando..." : "Crear entrenamiento"}
            </Button>
          </div>
        </form>
      </Card>
      )}
    </div>
  );
};
