import React, { useContext, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateCategory } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";
import { Layers, Pencil } from "lucide-react";
import { AssignedBadge } from "../../component/ui/readOnlyNotice";
import { isScopedCoach } from "../../utils/coachAccess";

import "../../../styles/teams.css";

export const Categories = () => {
  const { store, actions } = useContext(Context);
  const returnFocusRef = useRef(null);
  const [showForm, setShowForm] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [categoryName, setCategoryName] = useState("");
  const [categoryDescription, setCategoryDescription] = useState("");
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [editCategoryName, setEditCategoryName] = useState("");
  const [editCategoryDescription, setEditCategoryDescription] = useState("");
  const [loadingEdit, setLoadingEdit] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [categoryRetryKey, setCategoryRetryKey] = useState(0);
  const [deletingCategory, setDeletingCategory] = useState(false);
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
  const showMyTeams = isScopedCoach(store);
  const myTeams = (store.teams || []).filter((team) => team.is_assigned);

  useEffect(() => {
    if (showMyTeams) actions.getTeams({ seasonId });
  }, [showMyTeams, seasonId]);

  useEffect(() => {
    const loadCategories = async () => {
      if (!store.token) {
        setLoadingCategories(false);
        return;
      }

      setLoadingCategories(true);
      const result = await actions.getCategories({ seasonId });
      setLoadError(result.ok ? null : result.code || "HTTP_ERROR");
      setLoadingCategories(false);
    };

    loadCategories();
  }, [store.token, seasonId, categoryRetryKey]);

  const handleCreateCategory = async (e) => {
    e.preventDefault();

    if (loading) return;

    setErrors({});

    const newErrors = validateCategory({
      name: categoryName,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);

    const result = await actions.createCategory(
      {
        name: categoryName.trim(),
        description: categoryDescription.trim(),
      },
      { seasonId },
    );

    setLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    closeCreateForm();
  };

  const openCreateForm = () => {
    returnFocusRef.current = document.activeElement;
    setShowForm(true);
    setEditingCategoryId(null);
    setErrors({});
  };

  const closeCreateForm = () => {
    setShowForm(false);
    setCategoryName("");
    setCategoryDescription("");
    setErrors({});
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  };

  const openEditCategory = (category) => {
    returnFocusRef.current = document.activeElement;
    setShowForm(false);
    setEditingCategoryId(category.id);
    setEditCategoryName(category.name || "");
    setEditCategoryDescription(category.description || "");
    setErrors({});
  };

  const closeEditCategory = () => {
    setEditingCategoryId(null);
    setEditCategoryName("");
    setEditCategoryDescription("");
    setErrors({});
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  };

  const handleUpdateCategory = async (e) => {
    e.preventDefault();

    if (loadingEdit) return;

    setErrors({});

    const newErrors = validateCategory({
      name: editCategoryName,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoadingEdit(true);

    const result = await actions.updateCategory(
      editingCategoryId,
      {
        name: editCategoryName.trim(),
        description: editCategoryDescription.trim(),
      },
      { seasonId },
    );

    setLoadingEdit(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    closeEditCategory();
  };

  const editingCategory = store.categories?.find(
    (category) => category.id === editingCategoryId,
  );
  const categoryNameChanged =
    editingCategory &&
    editCategoryName.trim() !== (editingCategory.name || "").trim();
  const categoryGeneralErrorCode = Object.keys(errors).find(
    (code) => !["CATEGORY_NAME_REQUIRED", "CATEGORY_ALREADY_EXISTS"].includes(code),
  );

  const handleDeleteCategory = async () => {
    if (!editingCategory?.can_delete || deletingCategory) return;

    const confirmed = window.confirm(
      `¿Eliminar la categoría ${editingCategory.name}?\n\nSolo se eliminará porque nunca ha tenido equipos.`,
    );
    if (!confirmed) return;

    setDeletingCategory(true);
    setErrors({});
    const result = await actions.deleteCategory(editingCategory.id, {
      seasonId,
    });
    setDeletingCategory(false);

    if (!result.ok) {
      setErrors({ [result.code || "HTTP_ERROR"]: true });
      return;
    }

    closeEditCategory();
  };

  if (loadingCategories) {
    return <p role="status">Cargando categorías...</p>;
  }

  return (
    <>
      <PageHeader
        tone="categories"
        icon={Layers}
        eyebrow="Estructura deportiva"
        title="Categorías y equipos"
        subtitle="Las categorías organizan permanentemente la estructura del club."
        actions={
          canManageStructure &&
          !showForm &&
          !editingCategoryId && (
            <Button onClick={openCreateForm}>+ Crear categoría</Button>
          )
        }
      />
      <SeasonSelector
        loading={loadingSeasons}
        error={seasonError}
        onChange={selectSeason}
        onRetry={reloadSeasons}
        seasons={seasons}
        selectedSeason={selectedSeason}
      />
      {!seasonError && selectedSeason && (
        <p className="season-context-copy">
          Mostrando equipos y deportistas de: <strong>{selectedSeason.name}</strong>
        </p>
      )}
      {!seasonError && !loadingSeasons && !selectedSeason && (
        <p className="season-context-copy">
          Las categorías siguen disponibles, pero no hay una temporada activa para mostrar conteos deportivos.
        </p>
      )}
      {loadError && (
        <Card className="page-error-state" role="alert">
          <p>{errorMessages[loadError] || "No se pudieron cargar las categorías."}</p>
          <Button
            variant="secondary"
            onClick={() => setCategoryRetryKey((current) => current + 1)}
          >
            Volver a intentar
          </Button>
        </Card>
      )}
      {showForm && (
        <Card>
          <h4>Nueva categoría</h4>

          <form onSubmit={handleCreateCategory} className="form">
            <FormField
              label="Nombre de la categoría"
              htmlFor="category-name"
              errorId="category-name-error"
              error={
                errors.CATEGORY_NAME_REQUIRED
                  ? errorMessages.CATEGORY_NAME_REQUIRED
                  : errors.CATEGORY_ALREADY_EXISTS
                  ? errorMessages.CATEGORY_ALREADY_EXISTS
                  : null
              }
            >
              <Input
                type="text"
                id="category-name"
                autoFocus
                aria-describedby={
                  errors.CATEGORY_NAME_REQUIRED || errors.CATEGORY_ALREADY_EXISTS
                    ? "category-name-error"
                    : undefined
                }
                placeholder="Ej: Iniciación, U12, U14, Juvenil..."
                value={categoryName}
                className={
                  errors.CATEGORY_NAME_REQUIRED ||
                  errors.CATEGORY_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setCategoryName(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    CATEGORY_NAME_REQUIRED: false,
                    CATEGORY_ALREADY_EXISTS: false,
                  }));
                }}
              />
            </FormField>

            <FormField label="Descripción opcional" htmlFor="category-description">
              <Input
                type="text"
                id="category-description"
                placeholder="Ej: Deportistas que están comenzando"
                value={categoryDescription}
                onChange={(e) => {
                  setCategoryDescription(e.target.value);
                }}
              />
            </FormField>

            {categoryGeneralErrorCode && (
              <p className="form-error" role="alert">
                {errorMessages[categoryGeneralErrorCode] ||
                  "No se pudo crear la categoría."}
              </p>
            )}

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

      {editingCategoryId && (
        <Card>
          <h4>Editar categoría</h4>

          <form onSubmit={handleUpdateCategory} className="form">
            <FormField
              label="Nombre de la categoría"
              htmlFor="edit-category-name"
              errorId="edit-category-name-error"
              error={
                errors.CATEGORY_NAME_REQUIRED
                  ? errorMessages.CATEGORY_NAME_REQUIRED
                  : errors.CATEGORY_ALREADY_EXISTS
                  ? errorMessages.CATEGORY_ALREADY_EXISTS
                  : null
              }
            >
              <Input
                type="text"
                id="edit-category-name"
                autoFocus
                aria-describedby={
                  errors.CATEGORY_NAME_REQUIRED || errors.CATEGORY_ALREADY_EXISTS
                    ? "edit-category-name-error"
                    : undefined
                }
                placeholder="Ej: Iniciación, U12, U14, Juvenil..."
                value={editCategoryName}
                className={
                  errors.CATEGORY_NAME_REQUIRED ||
                  errors.CATEGORY_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(e) => {
                  setEditCategoryName(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    CATEGORY_NAME_REQUIRED: false,
                    CATEGORY_ALREADY_EXISTS: false,
                  }));
                }}
              />
            </FormField>

            <FormField label="Descripción opcional" htmlFor="edit-category-description">
              <Input
                type="text"
                id="edit-category-description"
                placeholder="Ej: Deportistas que están comenzando"
                value={editCategoryDescription}
                onChange={(e) => {
                  setEditCategoryDescription(e.target.value);
                }}
              />
            </FormField>

            {categoryNameChanged && editingCategory?.has_historical_teams && (
              <p className="category-history-warning" role="note">
                Este nombre también se mostrará en temporadas anteriores.
              </p>
            )}

            {categoryGeneralErrorCode && (
              <p className="form-error" role="alert">
                {errorMessages[categoryGeneralErrorCode] ||
                  "No se pudo actualizar la categoría."}
              </p>
            )}

            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={closeEditCategory}
              >
                Cancelar
              </Button>

              <Button type="submit" disabled={loadingEdit}>
                {loadingEdit ? "Guardando..." : "Guardar cambios"}
              </Button>

              {editingCategory?.can_delete && (
                <Button
                  type="button"
                  variant="danger"
                  disabled={deletingCategory}
                  onClick={handleDeleteCategory}
                >
                  {deletingCategory ? "Eliminando..." : "Eliminar categoría"}
                </Button>
              )}
            </div>
          </form>
        </Card>
      )}
      {showMyTeams && (
        <section className="my-teams-section">
          <h4>Mis equipos</h4>

          {myTeams.length === 0 ? (
            <Card>
              <div className="empty-state">
                <h4>Aún no tienes equipos asignados</h4>
                <p>
                  Puedes consultar todos los equipos del club desde sus
                  categorías.
                </p>
              </div>
            </Card>
          ) : (
            <div className="teams-grid">
              {myTeams.map((team) => (
                <Card
                  key={team.id}
                  className="team-card team-card-shell category-card"
                >
                  <Link
                    className="team-card-link"
                    to={`/teams/${team.id}${seasonId ? `?season=${seasonId}` : ""}`}
                  >
                    <div className="category-card-header">
                      <h3 className="team-card-title">{team.name}</h3>
                      <AssignedBadge />
                    </div>

                    <p className="team-meta">
                      {team.category?.name || "Sin categoría"}
                      {team.status === "archived" ? " · Archivado" : ""}
                    </p>
                  </Link>
                </Card>
              ))}
            </div>
          )}

          <h4 className="my-teams-all-title">Todas las categorías</h4>
        </section>
      )}

      {!loadError &&
        !showForm &&
        !editingCategoryId &&
        (store.categories?.length === 0 ? (
          <Card>
            <div className="empty-state">
              <h4>Aún no tienes categorías</h4>
              {canManageStructure ? (
                <>
                  <p>
                    Crea una categoría y después podrás organizar sus equipos.
                  </p>
                  <Button onClick={openCreateForm}>Crear categoría</Button>
                </>
              ) : (
                <p>El dueño del club todavía no ha creado categorías.</p>
              )}
            </div>
          </Card>
        ) : (
          <div className="teams-grid">
            {store.categories?.map((category) => (
              <Card
                key={category.id}
                className="team-card team-card-shell category-card"
              >
                <Link
                  className={`team-card-link ${canManageStructure ? "has-card-action" : ""}`}
                  to={`/categories/${category.id}${seasonId ? `?season=${seasonId}` : ""}`}
                >
                  <div className="category-card-header">
                    <h3 className="team-card-title">{category.name}</h3>
                  </div>

                  {category.description && (
                    <p className="category-description">{category.description}</p>
                  )}

                  <p className="team-meta">
                    {selectedSeason?.name || "Sin temporada activa"} · {category.total_teams || 0} equipos ·{" "}
                    {category.total_players || 0} deportistas
                  </p>
                </Link>

                  {canManageStructure && (
                    <button
                      type="button"
                      className="category-edit-button"
                      aria-label={`Editar categoría ${category.name}`}
                      onClick={(e) => {
                        openEditCategory(category);
                      }}
                    >
                      <Pencil size={16} />
                    </button>
                  )}
              </Card>
            ))}
          </div>
        ))}
    </>
  );
};
