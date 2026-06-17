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
          {(errors.TEAM_NOT_FOUND ||
            errors.FORBIDDEN ||
            errors.CLUB_REQUIRED ||
            errors.SESSION_EXPIRED ||
            errors.NETWORK_ERROR) && (
            <p className="form-error">
              {errors.TEAM_NOT_FOUND
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
