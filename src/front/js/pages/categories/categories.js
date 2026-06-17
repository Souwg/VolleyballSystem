import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { validateCategory } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { Layers, Pencil } from "lucide-react";
import "../../../styles/teams.css";

export const Categories = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
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

  useEffect(() => {
    const loadCategories = async () => {
      if (!store.token) {
        setLoadingCategories(false);
        return;
      }

      setLoadingCategories(true);
      await actions.getCategories();
      setLoadingCategories(false);
    };

    loadCategories();
  }, [store.token]);

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

    const result = await actions.createCategory({
      name: categoryName.trim(),
      description: categoryDescription.trim(),
    });

    setLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    setCategoryName("");
    setCategoryDescription("");
    setShowForm(false);
    setErrors({});
  };

  const openCreateForm = () => {
    setShowForm(true);
    setEditingCategoryId(null);
    setErrors({});
  };

  const closeCreateForm = () => {
    setShowForm(false);
    setCategoryName("");
    setCategoryDescription("");
    setErrors({});
  };

  const openEditCategory = (category) => {
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

    const result = await actions.updateCategory(editingCategoryId, {
      name: editCategoryName.trim(),
      description: editCategoryDescription.trim(),
    });

    setLoadingEdit(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    closeEditCategory();
  };

  if (loadingCategories) {
    return <p>Cargando categorías...</p>;
  }

  return (
    <>
      <PageHeader
        tone="categories"
        icon={Layers}
        eyebrow="Estructura deportiva"
        title="Categorías y equipos"
        subtitle="Organiza el club por edades, niveles, géneros o grupos de entrenamiento."
        actions={
          !showForm &&
          !editingCategoryId && (
            <Button onClick={openCreateForm}>+ Crear categoría</Button>
          )
        }
      />
      {showForm && (
        <Card>
          <h4>Nueva categoría</h4>

          <form onSubmit={handleCreateCategory} className="form">
            <FormField
              label="Nombre de la categoría"
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

            <FormField label="Descripción opcional">
              <Input
                type="text"
                placeholder="Ej: Deportistas que están comenzando"
                value={categoryDescription}
                onChange={(e) => {
                  setCategoryDescription(e.target.value);
                }}
              />
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

      {editingCategoryId && (
        <Card>
          <h4>Editar categoría</h4>

          <form onSubmit={handleUpdateCategory} className="form">
            <FormField
              label="Nombre de la categoría"
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

            <FormField label="Descripción opcional">
              <Input
                type="text"
                placeholder="Ej: Deportistas que están comenzando"
                value={editCategoryDescription}
                onChange={(e) => {
                  setEditCategoryDescription(e.target.value);
                }}
              />
            </FormField>

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
            </div>
          </form>
        </Card>
      )}
      {!showForm &&
        !editingCategoryId &&
        (store.categories?.length === 0 ? (
          <Card>
            <h4>Aún no tienes categorías</h4>
            <p>Crea una categoría como Iniciación, U12, U14 o Juvenil.</p>

            <Button onClick={openCreateForm}>Crear categoría</Button>
          </Card>
        ) : (
          <div className="teams-grid">
            {store.categories?.map((category) => (
              <Card
                key={category.id}
                className="team-card card-interactive category-card"
                onClick={() => navigate(`/categories/${category.id}`)}
              >
                <div className="category-card-header">
                  <h3 className="team-card-title">{category.name}</h3>

                  <button
                    type="button"
                    className="category-edit-button"
                    aria-label={`Editar categoría ${category.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      openEditCategory(category);
                    }}
                  >
                    <Pencil size={16} />
                  </button>
                </div>

                <p className="team-meta">
                  {category.total_teams || 0} equipos ·{" "}
                  {category.total_players || 0} deportistas
                </p>
              </Card>
            ))}
          </div>
        ))}
    </>
  );
};
