import React, { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateTeam } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { Pencil } from "lucide-react";

import "../../../styles/teams.css";

export const CategoryDetail = () => {
  const { actions } = useContext(Context);
  const { category_id } = useParams();
  const navigate = useNavigate();

  const [category, setCategory] = useState(null);
  const [teams, setTeams] = useState([]);
  const [loadingCategory, setLoadingCategory] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [teamGender, setTeamGender] = useState("");
  const [errors, setErrors] = useState({});
  const [loadingSubmit, setLoadingSubmit] = useState(false);

  const [editingTeamId, setEditingTeamId] = useState(null);
  const [editTeamName, setEditTeamName] = useState("");
  const [editTeamGender, setEditTeamGender] = useState("");
  const [loadingEditTeam, setLoadingEditTeam] = useState(false);

  const loadCategoryDetail = async () => {
    setLoadingCategory(true);

    try {
      const result = await actions.getCategoryDetail(category_id);

      if (result.ok) {
        setCategory(result.data.category);
        setTeams(result.data.teams || []);
        return;
      }

      setCategory(null);
      setTeams([]);
    } finally {
      setLoadingCategory(false);
    }
  };
  useEffect(() => {
    loadCategoryDetail();
  }, [category_id]);

  const handleCreateTeam = async (e) => {
    e.preventDefault();

    if (loadingSubmit) return;

    setErrors({});

    const newErrors = validateTeam({
      name: teamName,
      gender: teamGender,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoadingSubmit(true);

    const result = await actions.createTeamInCategory(category_id, {
      name: teamName.trim(),
      gender: teamGender,
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    setTeamName("");
    setTeamGender("");
    setShowForm(false);
    setErrors({});

    await loadCategoryDetail();

    setLoadingSubmit(false);
  };

  const closeCreateForm = () => {
    setShowForm(false);
    setTeamName("");
    setTeamGender("");
    setErrors({});
  };

  const openEditTeam = (team) => {
    setShowForm(false);
    setEditingTeamId(team.id);
    setEditTeamName(team.name || "");
    setEditTeamGender(team.gender || "");
    setErrors({});
  };

  const closeEditTeam = () => {
    setEditingTeamId(null);
    setEditTeamName("");
    setEditTeamGender("");
    setErrors({});
  };

  const handleUpdateTeam = async (e) => {
    e.preventDefault();

    if (loadingEditTeam) return;

    setErrors({});

    const newErrors = validateTeam({
      name: editTeamName,
      gender: editTeamGender,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoadingEditTeam(true);

    const result = await actions.updateTeam(editingTeamId, {
      name: editTeamName.trim(),
      gender: editTeamGender,
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingEditTeam(false);
      return;
    }

    await loadCategoryDetail();

    closeEditTeam();
    setLoadingEditTeam(false);
  };

  if (loadingCategory) {
    return <p>Cargando categoría...</p>;
  }

  if (!category) {
    return <p>Categoría no encontrada.</p>;
  }

  return (
    <div className="team-detail-page">
      <PageHeader
        variant="detail"
        eyebrow="Categoría"
        title={category.name}
        subtitle={`${teams.length} ${
          teams.length === 1 ? "equipo" : "equipos"
        } dentro de esta categoría`}
        onBack={() => navigate("/categories")}
        actions={
          !showForm &&
          !editingTeamId && (
            <Button
              onClick={() => {
                setShowForm(true);
                setEditingTeamId(null);
                setErrors({});
              }}
            >
              + Crear equipo
            </Button>
          )
        }
      />

      {showForm && (
        <Card>
          <h4>Nuevo equipo</h4>

          <form onSubmit={handleCreateTeam} className="form">
            <FormField
              label="Nombre del equipo"
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
                placeholder="Ej: Iniciación A, U14 Femenino..."
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
              label="Género del equipo"
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

              <Button type="submit" disabled={loadingSubmit}>
                {loadingSubmit ? "Creando..." : "Crear equipo"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {editingTeamId && (
        <Card>
          <h4>Editar equipo</h4>

          <form onSubmit={handleUpdateTeam} className="form">
            <FormField
              label="Nombre del equipo"
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
                placeholder="Ej: Iniciación A, U14 Femenino..."
                value={editTeamName}
                className={
                  errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setEditTeamName(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    TEAM_NAME_REQUIRED: false,
                    TEAM_ALREADY_EXISTS: false,
                  }));
                }}
              />
            </FormField>

            <FormField
              label="Género del equipo"
              error={
                errors.INVALID_TEAM_GENDER
                  ? errorMessages.INVALID_TEAM_GENDER
                  : errors.TEAM_GENDER_HAS_PLAYERS
                  ? errorMessages.TEAM_GENDER_HAS_PLAYERS
                  : null
              }
            >
              <Select
                value={editTeamGender}
                className={
                  errors.INVALID_TEAM_GENDER || errors.TEAM_GENDER_HAS_PLAYERS
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setEditTeamGender(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    INVALID_TEAM_GENDER: false,
                    TEAM_GENDER_HAS_PLAYERS: false,
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
              <Button type="button" variant="secondary" onClick={closeEditTeam}>
                Cancelar
              </Button>

              <Button type="submit" disabled={loadingEditTeam}>
                {loadingEditTeam ? "Guardando..." : "Guardar cambios"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {!showForm &&
        !editingTeamId &&
        (teams.length === 0 ? (
          <Card>
            <h4>Aún no tienes equipos</h4>
            <p>Crea el primer equipo dentro de {category.name}.</p>
          </Card>
        ) : (
          <div className="teams-grid">
            {teams.map((team) => (
              <Card
                key={team.id}
                className="team-card card-interactive category-card"
                onClick={() => navigate(`/teams/${team.id}`)}
              >
                <div className="category-card-header">
                  <h3 className="team-card-title">{team.name}</h3>

                  <button
                    type="button"
                    className="category-edit-button"
                    aria-label={`Editar equipo ${team.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      openEditTeam(team);
                    }}
                  >
                    <Pencil size={16} />
                  </button>
                </div>

                <p className="team-meta">
                  {team.gender === "female"
                    ? "Femenino"
                    : team.gender === "male"
                    ? "Masculino"
                    : "Mixto"}{" "}
                  · {team.total_players || 0} deportistas
                </p>
              </Card>
            ))}
          </div>
        ))}
    </div>
  );
};
