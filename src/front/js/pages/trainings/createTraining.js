import React, { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { validateTraining } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";

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

  const handleGoBack = () => {
    navigate(-1);
  };

  const handleCreateTraining = async (e) => {
    e.preventDefault();

    if (loading) return;

    setErrors({});
    setLoading(true);

    const newErrors = validateTraining({
      team_id: selectedTeam,
      date,
      location,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      setLoading(false);
      return;
    }

    const result = await actions.createTraining({
      team_id: selectedTeam,
      date: date.trim(),
      location: location.trim(),
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }

    setLoading(false);
    navigate(`/trainings/${result.data.training.id}`);
  };

  return (
    <Container>
      <PageHeader
        title="Crear entrenamiento"
        subtitle="Registra un nuevo entrenamiento"
        actions={
          <Button className="button-secondary" onClick={handleGoBack}>
            ← Volver
          </Button>
        }
      />

      <Card>
        <h4>Detalles del entrenamiento</h4>
        <p>Completa la información básica</p>

        <form onSubmit={handleCreateTraining} className="form">
          {!team_id && (
            <>
              <label>Equipo</label>
              <select
                className={errors.TEAM_ID_REQUIRED ? "input-error" : ""}
                value={selectedTeam}
                onChange={(e) => {
                  setSelectedTeam(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    TEAM_ID_REQUIRED: false,
                  }));
                }}
              >
                <option value="">Selecciona un equipo</option>

                {store.teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
              {errors.TEAM_ID_REQUIRED && (
                <p className="form-error">{errorMessages.TEAM_ID_REQUIRED}</p>
              )}
            </>
          )}
          <label>Fecha</label>
          <Input
            type="date"
            value={date}
            className={errors.TRAINING_DATE_REQUIRED ? "input-error" : ""}
            onChange={(e) => {
              setDate(e.target.value);
              setErrors((prev) => ({
                ...prev,
                TRAINING_DATE_REQUIRED: false,
              }));
            }}
          />
          {errors.TRAINING_DATE_REQUIRED && (
            <p className="form-error">{errorMessages.TRAINING_DATE_REQUIRED}</p>
          )}
          <label>Ubicación</label>
          <Input
            type="text"
            placeholder="Ej: Cancha central, Gimnasio..."
            value={location}
            className={errors.TRAINING_LOCATION_REQUIRED ? "input-error" : ""}
            onChange={(e) => {
              setLocation(e.target.value);
              setErrors((prev) => ({
                ...prev,
                TRAINING_LOCATION_REQUIRED: false,
              }));
            }}
          />
          {errors.TRAINING_LOCATION_REQUIRED && (
            <p className="form-error">
              {errorMessages.TRAINING_LOCATION_REQUIRED}
            </p>
          )}

          <div className="form-actions">
            <Button type="submit" className="button-primary" disabled={loading}>
              {loading ? "Creando..." : "Crear entrenamiento"}
            </Button>
          </div>
        </form>
      </Card>
    </Container>
  );
};
