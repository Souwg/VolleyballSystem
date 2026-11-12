import React, { useContext, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import {
  AssignedBadge,
  ReadOnlyNotice,
} from "../../component/ui/readOnlyNotice";
import { isScopedCoach } from "../../utils/coachAccess";
import { validateTeam } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { Pencil } from "lucide-react";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";

import "../../../styles/teams.css";

export const CategoryDetail = () => {
  const { store, actions } = useContext(Context);
  const { category_id } = useParams();
  const navigate = useNavigate();
  const returnFocusRef = useRef(null);

  const [category, setCategory] = useState(null);
  const [teams, setTeams] = useState([]);
  const [loadingCategory, setLoadingCategory] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [categorySeason, setCategorySeason] = useState(null);

  const [showForm, setShowForm] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [teamGender, setTeamGender] = useState("");
  const [errors, setErrors] = useState({});
  const [loadingSubmit, setLoadingSubmit] = useState(false);

  const [editingTeamId, setEditingTeamId] = useState(null);
  const [editTeamName, setEditTeamName] = useState("");
  const [editTeamGender, setEditTeamGender] = useState("");
  const [loadingEditTeam, setLoadingEditTeam] = useState(false);
  const {
    loadingSeasons,
    reloadSeasons,
    seasonId,
    seasons,
    selectedSeason,
    seasonError,
    selectSeason,
  } = useSeasonSelection();
  const canManageStructure = store.user?.role === "club_owner";
  const contextSeason = selectedSeason || categorySeason;
  const canPrepareTeams = ["active", "planned"].includes(
    contextSeason?.status,
  );
  const showAssignment = isScopedCoach(store);
  // Mis equipos primero; los demás siguen visibles para consulta.
  const orderedTeams = showAssignment
    ? [...teams].sort(
        (first, second) =>
          Number(Boolean(second.is_assigned)) -
          Number(Boolean(first.is_assigned)),
      )
    : teams;

  const loadCategoryDetail = async () => {
    setLoadingCategory(true);

    try {
      const result = await actions.getCategoryDetail(category_id, { seasonId });

      if (result.ok) {
        let nextTeams = result.data.teams || [];

        // Sin temporada explícita solo llegan los activos: el Owner necesita
        // ver los archivados de la temporada activa para poder reactivarlos.
        if (canManageStructure && !seasonId && result.data.season) {
          const explicit = await actions.getCategoryDetail(category_id, {
            seasonId: result.data.season.id,
          });

          if (explicit.ok) {
            nextTeams = [
              ...nextTeams,
              ...(explicit.data.teams || []).filter(
                (team) => team.status === "archived",
              ),
            ];
          }
        }

        setCategory(result.data.category);
        setCategorySeason(result.data.season || null);
        setTeams(nextTeams);
        setLoadError(null);
        return;
      }

      setCategory(null);
      setCategorySeason(null);
      setTeams([]);
      setLoadError(result.code || "HTTP_ERROR");
    } finally {
      setLoadingCategory(false);
    }
  };
  useEffect(() => {
    loadCategoryDetail();
  }, [category_id, seasonId]);

  useEffect(() => {
    if (!canPrepareTeams) {
      setShowForm(false);
      setEditingTeamId(null);
    }
  }, [canPrepareTeams]);

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
      ...(contextSeason?.status === "planned"
        ? { season_id: contextSeason.id }
        : {}),
    });

    if (!result.ok) {
      setErrors({ [result.code]: true });
      setLoadingSubmit(false);
      return;
    }

    closeCreateForm();

    await loadCategoryDetail();

    setLoadingSubmit(false);
  };

  const closeCreateForm = () => {
    setShowForm(false);
    setTeamName("");
    setTeamGender("");
    setErrors({});
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  };

  const openEditTeam = (team) => {
    returnFocusRef.current = document.activeElement;
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
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
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
    return <p role="status">Cargando categoría...</p>;
  }

  if (!category) {
    return (
      <Card className="page-error-state" role="alert">
        <p>
          {loadError === "CATEGORY_NOT_FOUND"
            ? "Categoría no encontrada."
            : errorMessages[loadError] || "No se pudo cargar la categoría."}
        </p>
        <Button variant="secondary" onClick={loadCategoryDetail}>
          Volver a intentar
        </Button>
      </Card>
    );
  }

  const teamGeneralErrorCode = Object.keys(errors).find(
    (code) =>
      ![
        "TEAM_NAME_REQUIRED",
        "TEAM_ALREADY_EXISTS",
        "INVALID_TEAM_GENDER",
        "TEAM_GENDER_HAS_PLAYERS",
      ].includes(code),
  );

  return (
    <>
      <nav className="breadcrumbs" aria-label="Migas de pan">
        <Link to={`/categories${seasonId ? `?season=${seasonId}` : ""}`}>
          Categorías
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{category.name}</span>
      </nav>
      <PageHeader
        variant="detail"
        eyebrow="Categoría"
        title={category.name}
        subtitle={
          contextSeason
            ? `Equipos en ${contextSeason.name} · ${
                contextSeason.status === "active"
                  ? "Activa"
                  : contextSeason.status === "planned"
                  ? "Planificada"
                  : "Cerrada"
              }`
            : "Sin temporada activa para mostrar equipos"
        }
        onBack={() =>
          navigate(`/categories${seasonId ? `?season=${seasonId}` : ""}`)
        }
        actions={
          canManageStructure &&
          !showForm &&
          canPrepareTeams &&
          !editingTeamId && (
            <Button
              onClick={() => {
                returnFocusRef.current = document.activeElement;
                setShowForm(true);
                setEditingTeamId(null);
                setErrors({});
              }}
            >
              + Crear equipo{contextSeason ? ` en ${contextSeason.name}` : ""}
            </Button>
          )
        }
      />
      {category.description && (
        <p className="category-detail-description">{category.description}</p>
      )}
      <SeasonSelector
        loading={loadingSeasons}
        error={seasonError}
        onChange={selectSeason}
        onRetry={reloadSeasons}
        seasons={seasons}
        selectedSeason={selectedSeason}
      />
      {contextSeason?.status === "planned" && (
        <div className="season-structure-notice" role="note">
          Preparación · {contextSeason.name} — Planificada. Puedes crear y editar equipos antes de activarla.
        </div>
      )}
      {contextSeason?.status === "closed" && (
        <ReadOnlyNotice>
          Histórico · {contextSeason.name} — Cerrada. Esta información es de solo consulta.
        </ReadOnlyNotice>
      )}
      <div className="team-detail-page">
        {showForm && (
          <Card>
            <h4>Nuevo equipo</h4>
              <div className="team-form-context">
                <span>Categoría: {category.name}</span>
                <span>
                  Temporada: {contextSeason?.name || "Sin temporada"} — {contextSeason?.status === "planned" ? "Planificada" : "Activa"}
                </span>
              </div>

            <form onSubmit={handleCreateTeam} className="form">
              <FormField
                label="Nombre del equipo"
                htmlFor="team-name"
                errorId="team-name-error"
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
                  id="team-name"
                  autoFocus
                  aria-describedby={
                    errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                      ? "team-name-error"
                      : undefined
                  }
                  placeholder="Ej: A"
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

              {teamGeneralErrorCode && (
                <p className="form-error" role="alert">
                  {errorMessages[teamGeneralErrorCode] ||
                    "No se pudo crear el equipo."}
                </p>
              )}

              <FormField
                label="Rama"
                htmlFor="team-gender"
                errorId="team-gender-error"
                error={
                  errors.INVALID_TEAM_GENDER
                    ? errorMessages.INVALID_TEAM_GENDER
                    : null
                }
              >
                <Select
                  value={teamGender}
                  id="team-gender"
                  aria-describedby={
                    errors.INVALID_TEAM_GENDER ? "team-gender-error" : undefined
                  }
                  className={errors.INVALID_TEAM_GENDER ? "input-error" : ""}
                  onChange={(e) => {
                    setTeamGender(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      INVALID_TEAM_GENDER: false,
                    }));
                  }}
                >
                  <option value="">Selecciona la rama</option>
                  <option value="female">Femenina</option>
                  <option value="male">Masculina</option>
                  <option value="mixed">Mixta</option>
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
              <div className="team-form-context">
                <span>Categoría: {category.name}</span>
                <span>
                  Temporada: {contextSeason?.name || "Sin temporada"} — {contextSeason?.status === "planned" ? "Planificada" : "Activa"}
                </span>
              </div>

            <form onSubmit={handleUpdateTeam} className="form">
              <FormField
                label="Nombre del equipo"
                htmlFor="edit-team-name"
                errorId="edit-team-name-error"
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
                  id="edit-team-name"
                  autoFocus
                  aria-describedby={
                    errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                      ? "edit-team-name-error"
                      : undefined
                  }
                  placeholder="Ej: A"
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
                label="Rama"
                htmlFor="edit-team-gender"
                errorId="edit-team-gender-error"
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
                  id="edit-team-gender"
                  aria-describedby={
                    errors.INVALID_TEAM_GENDER || errors.TEAM_GENDER_HAS_PLAYERS
                      ? "edit-team-gender-error"
                      : undefined
                  }
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
                  <option value="">Selecciona la rama</option>
                  <option value="female">Femenina</option>
                  <option value="male">Masculina</option>
                  <option value="mixed">Mixta</option>
                </Select>
              </FormField>

              {teamGeneralErrorCode && (
                <p className="form-error" role="alert">
                  {errorMessages[teamGeneralErrorCode] ||
                    "No se pudo actualizar el equipo."}
                </p>
              )}

              <div className="form-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeEditTeam}
                >
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
              <div className="empty-state">
                <h4>
                  {contextSeason?.status === "closed"
                    ? "Sin equipos en esta temporada"
                    : "Aún no hay equipos"}
                </h4>
                {contextSeason?.status === "closed" ? (
                  <p>No hubo equipos de esta categoría en esta temporada.</p>
                ) : canManageStructure && canPrepareTeams ? (
                  <>
                    <p>Crea el primer equipo dentro de {category.name}.</p>
                    <Button
                      onClick={() => {
                        returnFocusRef.current = document.activeElement;
                        setShowForm(true);
                      }}
                    >
                      Crear equipo
                    </Button>
                  </>
                ) : (
                  <p>No hay equipos para mostrar en este contexto.</p>
                )}
              </div>
            </Card>
          ) : (
            <div className="teams-grid">
              {orderedTeams.map((team) => (
                <Card
                  key={team.id}
                  className="team-card team-card-shell category-card"
                >
                  <Link
                    className={`team-card-link ${canManageStructure ? "has-card-action" : ""}`}
                    to={`/teams/${team.id}${seasonId ? `?season=${seasonId}` : ""}`}
                  >
                    <div className="category-card-header">
                      <h3 className="team-card-title">{team.name}</h3>
                      {showAssignment && team.is_assigned && <AssignedBadge />}
                    </div>

                    <p className="team-meta">
                      {contextSeason?.name || "Sin temporada"} · {contextSeason?.status === "planned" ? "Planificada" : contextSeason?.status === "closed" ? "Cerrada" : "Activa"} · Rama {team.gender === "female" ? "femenina" : team.gender === "male" ? "masculina" : "mixta"} · {team.total_players || 0} deportistas
                      {team.status === "archived" ? " · Archivado" : ""}
                    </p>
                  </Link>

                    {canManageStructure && canPrepareTeams && team.status !== "archived" && (
                      <button
                        type="button"
                        className="category-edit-button"
                        aria-label={`Editar equipo ${team.name}`}
                        onClick={(e) => {
                          openEditTeam(team);
                        }}
                      >
                        <Pencil size={16} />
                      </button>
                    )}
                </Card>
              ))}
            </div>
          ))}
      </div>
    </>
  );
};
