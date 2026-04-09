import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
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
    setErrors({});
  };

  if (loadingTeams) {
    return <p>Cargando categorías...</p>;
  }

  return (
    <>
      <PageHeader title="Equipos" subtitle="Gestiona los equipos de tu club" />
      {!showForm && (
        <Button className="button-primary" onClick={openCreateForm}>
          + Crear equipo
        </Button>
      )}
      {showForm && (
        <Card>
          <h4>Nuevo equipo</h4>

          <form onSubmit={handleCreateTeam} className="form">
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

            {errors.TEAM_NAME_REQUIRED && (
              <p className="form-error">{errorMessages.TEAM_NAME_REQUIRED}</p>
            )}

            {errors.TEAM_ALREADY_EXISTS && (
              <p className="form-error">{errorMessages.TEAM_ALREADY_EXISTS}</p>
            )}

            <select
              className={`select ${
                errors.INVALID_TEAM_GENDER ? "input-error" : ""
              }`}
              value={teamGender}
              onChange={(e) => {
                setTeamGender(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  INVALID_TEAM_GENDER: false,
                }));
              }}
            >
              <option value="">Selecciona la rama</option>
              <option value="female">Femenino</option>
              <option value="male">Masculino</option>
              <option value="mixed">Mixto</option>
            </select>

            <div className="form-actions">
              <Button
                type="button"
                className="button-secondary"
                onClick={closeCreateForm}
              >
                Cancelar
              </Button>

              <Button type="submit" disabled={loading}>
                {loading ? "Creando..." : "Crear equipo"}
              </Button>
            </div>
          </form>
        </Card>
      )}
      {!showForm &&
        (store.teams.length === 0 ? (
          <Card>
            <h4>Aún no tienes equipos</h4>
            <p>Crea tu primer equipo para empezar</p>

            <Button className="button-primary" onClick={openCreateForm}>
              Crear equipo
            </Button>
          </Card>
        ) : (
          <div className="teams-grid">
            {store.teams.map((team) => (
              <Card key={team.id} onClick={() => navigate(`/teams/${team.id}`)}>
                <h5>{team.name}</h5>
                <p className="team-meta">
                  {team.gender === "female"
                    ? "Femenina"
                    : team.gender === "male"
                    ? "Masculina"
                    : "Mixta"}
                </p>
              </Card>
            ))}
          </div>
        ))}
    </>
  );
};
