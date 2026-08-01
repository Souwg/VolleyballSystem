import React, { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { validateTraining } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";

export const CreateTraining = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const { team_id } = useParams();

  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [location, setLocation] = useState("");
  const [selectedTeam, setSelectedTeam] = useState(team_id || "");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const loadTeams = async () => {
    if (team_id) return;
    await actions.getTeams();
  };

  useEffect(() => {
    loadTeams();
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

  return (
    <div className="training-form-page">
      <PageHeader
        variant="detail"
        eyebrow="Entrenamiento"
        title="Crear entrenamiento"
        subtitle="Registra una nueva sesión para una categoría."
        onBack={() =>
          navigate(team_id ? `/teams/${team_id}/trainings` : "/trainings")
        }
      />

      <Card>
        <h4>Detalles del entrenamiento</h4>
        <p>Completa la información básica</p>

        <form onSubmit={handleCreateTraining} className="form">
          {!team_id && (
            <FormField
              label="Categoría"
              error={
                errors.TEAM_ID_REQUIRED ? errorMessages.TEAM_ID_REQUIRED : null
              }
            >
              <Select
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

                {store.teams.map((team) => (
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
            error={
              errors.TRAINING_DATE_REQUIRED
                ? errorMessages.TRAINING_DATE_REQUIRED
                : null
            }
          >
            <Input
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
              error={
                errors.TRAINING_START_TIME_REQUIRED
                  ? errorMessages.TRAINING_START_TIME_REQUIRED
                  : null
              }
            >
              <Input
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
              error={
                errors.TRAINING_END_TIME_REQUIRED
                  ? errorMessages.TRAINING_END_TIME_REQUIRED
                  : errors.INVALID_TRAINING_TIME_RANGE
                  ? errorMessages.INVALID_TRAINING_TIME_RANGE
                  : null
              }
            >
              <Input
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
            helper="Ej: Cancha central, Gimnasio municipal, Colegio..."
            error={
              errors.TRAINING_LOCATION_REQUIRED
                ? errorMessages.TRAINING_LOCATION_REQUIRED
                : null
            }
          >
            <Input
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
          {(errors.INVALID_TIME_FORMAT ||
            errors.TEAM_NOT_FOUND ||
            errors.FORBIDDEN ||
            errors.CLUB_REQUIRED ||
            errors.SESSION_EXPIRED ||
            errors.NETWORK_ERROR) && (
            <p className="form-error">
              {errors.INVALID_TIME_FORMAT
                ? errorMessages.INVALID_TIME_FORMAT
                : errors.TEAM_NOT_FOUND
                ? errorMessages.TEAM_NOT_FOUND
                : errors.FORBIDDEN
                ? errorMessages.FORBIDDEN
                : errors.CLUB_REQUIRED
                ? errorMessages.CLUB_REQUIRED
                : errors.SESSION_EXPIRED
                ? errorMessages.SESSION_EXPIRED
                : errorMessages.NETWORK_ERROR}
            </p>
          )}

          <div className="form-actions">
            <Button type="submit" disabled={loading}>
              {loading ? "Creando..." : "Crear entrenamiento"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
