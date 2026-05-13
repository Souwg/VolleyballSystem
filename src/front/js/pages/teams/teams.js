import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateTeam } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

import "../../../styles/teams.css";

export const Teams = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [teamName, setTeamName] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [loadingTeams, setLoadingTeams] = useState(true);
  const [teamGender, setTeamGender] = useState("");

  useEffect(() => {
    const loadTeams = async () => {
      if (!store.token) return;

      setLoadingTeams(true);
      await actions.getTeams();
      setLoadingTeams(false);
    };

    loadTeams();
  }, [store.token]);

  const handleCreateTeam = async (e) => {
    e.preventDefault();

    if (loading) return;

    setErrors({});
    setLoading(true);

    const newErrors = validateTeam({
      name: teamName,
      gender: teamGender,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      setLoading(false);
      return;
    }

    const cleanName = teamName.trim();

    const result = await actions.createTeam({
      name: cleanName,
      gender: teamGender,
    });

    setLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }
    setTeamName("");
    setTeamGender("");
    setShowForm(false);
    setErrors({});
  };

  const openCreateForm = () => {
    setShowForm(true);
    setErrors({});
  };

  const closeCreateForm = () => {
    setShowForm(false);
    setTeamName("");
    setTeamGender("");
    setErrors({});
  };

  if (loadingTeams) {
    return <p>Cargando categorías...</p>;
  }

  return (
    <>
      <PageHeader
        eyebrow="Gestión del club"
        title="Categorías"
        subtitle="Organiza los equipos por género, nivel o etapa deportiva."
        actions={
          !showForm && (
            <Button onClick={openCreateForm}>+ Crear categoría</Button>
          )
        }
      />
      {showForm && (
        <Card>
          <h4>Nueva categoría</h4>

          <form onSubmit={handleCreateTeam} className="form">
            <FormField
              label="Categoría"
              error={
                errors.TEAM_NAME_REQUIRED
                  ? errorMessages.TEAM_NAME_REQUIRED
                  : errors.TEAM_ALREADY_EXISTS
                  ? errorMessages.TEAM_ALREADY_EXISTS
                  : null
              }
            >
              <Input
                type="text"
                placeholder="Ej: Sub12, Juvenil..."
                value={teamName}
                className={
                  errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setTeamName(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    TEAM_NAME_REQUIRED: false,
                    TEAM_ALREADY_EXISTS: false,
                  }));
                }}
              />
            </FormField>

            <FormField
              label="Género"
              error={
                errors.INVALID_TEAM_GENDER
                  ? errorMessages.INVALID_TEAM_GENDER
                  : null
              }
            >
              <Select
                value={teamGender}
                className={errors.INVALID_TEAM_GENDER ? "input-error" : ""}
                onChange={(e) => {
                  setTeamGender(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    INVALID_TEAM_GENDER: false,
                  }));
                }}
              >
                <option value="">Selecciona el género</option>
                <option value="female">Femenino</option>
                <option value="male">Masculino</option>
                <option value="mixed">Mixto</option>
              </Select>
            </FormField>

            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={closeCreateForm}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "Creando..." : "Crear categoría"}
              </Button>
            </div>
          </form>
        </Card>
      )}
      {!showForm &&
        (store.teams.length === 0 ? (
          <Card>
            <h4>Aún no tienes categorías</h4>
            <p>Crea tu primera categoría para empezar</p>

            <Button onClick={openCreateForm}>Crear categoría</Button>
          </Card>
        ) : (
          <div className="teams-grid">
            {store.teams.map((team) => (
              <Card
                key={team.id}
                className="team-card card-interactive"
                onClick={() => navigate(`/teams/${team.id}`)}
              >
                <h3 className="team-card-title">{team.name}</h3>

                <p className="team-meta">
                  {team.gender === "female"
                    ? "Femenino"
                    : team.gender === "male"
                    ? "Masculino"
                    : "Mixto"}
                </p>
              </Card>
            ))}
          </div>
        ))}
    </>
  );
};
