import React, { useContext, useEffect, useState } from "react";
import { Users as UsersIcon } from "lucide-react";

import { Context } from "../../store/appContext";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { FormField } from "../../component/ui/formField";
import { Input } from "../../component/ui/input";
import { PageHeader } from "../../component/ui/pageHeader";
import { Select } from "../../component/ui/select";
import { useToast } from "../../../../context/toastContext";
import { errorMessages } from "../../utils/errorMessages";
import { validateClubUser } from "../../utils/validators";
import { getPublicLoginUrl } from "../../utils/publicUrls";

import "../../../styles/clubUsers.css";

const EMPTY_FORM = {
  full_name: "",
  email: "",
  role: "coach",
};

const ROLE_LABELS = {
  coach: "Entrenador",
  staff: "Personal administrativo",
};

const getRoleLabel = (role) => ROLE_LABELS[role] || role;

export const ClubUsers = () => {
  const { store, actions } = useContext(Context);
  const { showToast } = useToast();
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [statusLoadingId, setStatusLoadingId] = useState(null);
  const [createdCredentials, setCreatedCredentials] = useState(null);

  useEffect(() => {
    let mounted = true;

    const loadUsers = async () => {
      setLoadingUsers(true);
      setLoadError("");

      const result = await actions.getClubUsers();

      if (!mounted) return;

      if (!result?.ok) {
        setLoadError(
          result?.message || "No se pudieron cargar los usuarios del club."
        );
      }

      setLoadingUsers(false);
    };

    loadUsers();

    return () => {
      mounted = false;
    };
  }, []);

  const resetForm = () => {
    setShowForm(false);
    setEditingUser(null);
    setForm(EMPTY_FORM);
    setErrors({});
    setFormError("");
  };

  const openCreateForm = () => {
    setEditingUser(null);
    setForm(EMPTY_FORM);
    setErrors({});
    setFormError("");
    setShowForm(true);
  };

  const openEditForm = (user) => {
    setEditingUser(user);
    setForm({
      full_name: user.full_name,
      email: user.email,
      role: user.role,
    });
    setErrors({});
    setFormError("");
    setShowForm(true);
  };

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({
      ...current,
      FULL_NAME_REQUIRED:
        field === "full_name" ? false : current.FULL_NAME_REQUIRED,
      EMAIL_REQUIRED: field === "email" ? false : current.EMAIL_REQUIRED,
      INVALID_EMAIL: field === "email" ? false : current.INVALID_EMAIL,
      EMAIL_ALREADY_EXISTS:
        field === "email" ? false : current.EMAIL_ALREADY_EXISTS,
      INVALID_ROLE: field === "role" ? false : current.INVALID_ROLE,
    }));
    setFormError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (submitting) return;

    const validationErrors = validateClubUser(form);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    const payload = {
      full_name: form.full_name.trim(),
      email: form.email.trim().toLowerCase(),
      role: form.role,
    };

    if (editingUser && editingUser.role !== payload.role) {
      const confirmed = window.confirm(
        "El usuario deberá iniciar sesión nuevamente para aplicar el nuevo rol. ¿Deseas continuar?"
      );

      if (!confirmed) return;
    }

    setSubmitting(true);
    setErrors({});
    setFormError("");

    const result = editingUser
      ? await actions.updateClubUser(editingUser.id, payload)
      : await actions.createClubUser(payload);

    if (!result?.ok) {
      setErrors({ [result?.code || "UNKNOWN_ERROR"]: true });
      setFormError(result?.message || "No se pudo guardar el usuario.");
      setSubmitting(false);
      return;
    }

    if (!editingUser) {
      setCreatedCredentials({
        fullName: result.data.user.full_name,
        email: result.data.user.email,
        role: result.data.user.role,
        password: result.data.temporary_password,
      });
    }

    resetForm();
    setSubmitting(false);
  };

  const copyToClipboard = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      showToast("Copiado al portapapeles", "success");
    } catch (error) {
      showToast("No se pudo copiar", "error");
    }
  };

  const copyCredentials = () => {
    const loginUrl = getPublicLoginUrl();
    const text = [
      "Credenciales de SportFlow",
      `Nombre: ${createdCredentials.fullName}`,
      `Correo: ${createdCredentials.email}`,
      `Rol: ${getRoleLabel(createdCredentials.role)}`,
      `Contraseña temporal: ${createdCredentials.password}`,
      `Ingresar en: ${loginUrl}`,
      "En el primer acceso deberá crear una nueva contraseña.",
    ].join("\n");

    copyToClipboard(text);
  };

  const closeCredentials = () => {
    const confirmed = window.confirm(
      "Asegúrate de haber guardado o compartido las credenciales. La contraseña temporal no volverá a mostrarse."
    );

    if (confirmed) {
      setCreatedCredentials(null);
    }
  };

  const changeStatus = async (user) => {
    if (statusLoadingId) return;

    const action = user.is_active ? "desactivar" : "reactivar";
    const prompt = user.is_active
      ? "Este usuario dejará de poder acceder a SportFlow. Su historial no se eliminará. ¿Deseas continuar?"
      : "El usuario podrá volver a iniciar sesión con su contraseña actual. ¿Deseas reactivarlo?";

    if (!window.confirm(prompt)) return;

    setStatusLoadingId(user.id);
    setLoadError("");

    const result = user.is_active
      ? await actions.deactivateClubUser(user.id)
      : await actions.activateClubUser(user.id);

    if (!result?.ok) {
      setLoadError(result?.message || `No se pudo ${action} el usuario.`);
    }

    setStatusLoadingId(null);
  };

  const renderStatus = (user) => (
    <div className="club-user-status-stack">
      <span
        className={`status-badge ${
          user.is_active ? "status-success" : "status-danger"
        }`}
      >
        {user.is_active ? "Activo" : "Inactivo"}
      </span>
      {user.first_login && (
        <span className="club-user-first-login">Primer acceso pendiente</span>
      )}
    </div>
  );

  const renderActions = (user) => {
    const changingStatus = statusLoadingId === user.id;

    return (
      <div className="club-user-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={submitting || Boolean(statusLoadingId)}
          onClick={() => openEditForm(user)}
        >
          Editar
        </Button>
        <Button
          type="button"
          variant={user.is_active ? "danger" : "primary"}
          disabled={Boolean(statusLoadingId) || submitting}
          onClick={() => changeStatus(user)}
        >
          {changingStatus
            ? "Guardando..."
            : user.is_active
            ? "Desactivar"
            : "Reactivar"}
        </Button>
      </div>
    );
  };

  return (
    <>
      <PageHeader
        icon={UsersIcon}
        eyebrow="Configuración del club"
        title="Usuarios del club"
        subtitle="Administra entrenadores y personal administrativo sin alterar su historial."
        actions={
          !showForm && (
            <Button type="button" onClick={openCreateForm}>
              + Agregar usuario
            </Button>
          )
        }
      />

      {showForm && (
        <Card className="club-user-form-card">
          <div className="club-user-section-heading">
            <div>
              <h2>{editingUser ? "Editar usuario" : "Nuevo usuario"}</h2>
              <p>
                {editingUser
                  ? "Actualiza los datos y permisos del usuario."
                  : "Crea un acceso opcional para un entrenador o personal administrativo."}
              </p>
            </div>
          </div>

          <form className="form" onSubmit={handleSubmit}>
            <div className="club-user-form-grid">
              <FormField
                label="Nombre completo"
                error={
                  errors.FULL_NAME_REQUIRED
                    ? errorMessages.FULL_NAME_REQUIRED
                    : null
                }
              >
                <Input
                  value={form.full_name}
                  autoComplete="name"
                  placeholder="Ej: Ana Martínez"
                  className={errors.FULL_NAME_REQUIRED ? "input-error" : ""}
                  onChange={(event) =>
                    updateField("full_name", event.target.value)
                  }
                />
              </FormField>

              <FormField
                label="Correo electrónico"
                error={
                  errors.EMAIL_ALREADY_EXISTS
                    ? errorMessages.EMAIL_ALREADY_EXISTS
                    : errors.EMAIL_REQUIRED
                    ? errorMessages.EMAIL_REQUIRED
                    : errors.INVALID_EMAIL
                    ? errorMessages.INVALID_EMAIL
                    : null
                }
              >
                <Input
                  type="email"
                  value={form.email}
                  autoComplete="email"
                  placeholder="Ej: usuario@email.com"
                  className={
                    errors.EMAIL_ALREADY_EXISTS ||
                    errors.EMAIL_REQUIRED ||
                    errors.INVALID_EMAIL
                      ? "input-error"
                      : ""
                  }
                  onChange={(event) => updateField("email", event.target.value)}
                />
              </FormField>

              <FormField
                label="Rol"
                error={errors.INVALID_ROLE ? errorMessages.INVALID_ROLE : null}
                helper="El rol determina las áreas disponibles dentro de SportFlow."
              >
                <Select
                  value={form.role}
                  className={errors.INVALID_ROLE ? "input-error" : ""}
                  onChange={(event) => updateField("role", event.target.value)}
                >
                  <option value="coach">Entrenador</option>
                  <option value="staff">Personal administrativo</option>
                </Select>
              </FormField>
            </div>

            {formError && <p className="club-user-inline-error">{formError}</p>}

            <div className="form-actions club-user-form-actions">
              <Button type="submit" disabled={submitting}>
                {submitting
                  ? "Guardando..."
                  : editingUser
                  ? "Guardar cambios"
                  : "Crear usuario"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={submitting}
                onClick={resetForm}
              >
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      {loadError && <p className="club-user-inline-error">{loadError}</p>}

      {loadingUsers ? (
        <Card className="club-users-loading">Cargando usuarios...</Card>
      ) : store.clubUsers.length === 0 ? (
        <Card className="empty-state club-users-empty">
          <UsersIcon size={30} aria-hidden="true" />
          <h4>Aún no has agregado usuarios al club.</h4>
          <p>
            Puedes administrar SportFlow como Owner y agregar colaboradores
            cuando los necesites.
          </p>
          {!showForm && (
            <Button type="button" onClick={openCreateForm}>
              Agregar usuario
            </Button>
          )}
        </Card>
      ) : (
        <>
          <Card className="club-users-table-card">
            <div className="club-users-table-wrap">
              <table className="club-users-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Email</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {store.clubUsers.map((user) => (
                    <tr
                      key={user.id}
                      className={!user.is_active ? "is-inactive" : ""}
                    >
                      <td data-label="Nombre">{user.full_name}</td>
                      <td data-label="Email">{user.email}</td>
                      <td data-label="Rol">{getRoleLabel(user.role)}</td>
                      <td data-label="Estado">{renderStatus(user)}</td>
                      <td data-label="Acciones">{renderActions(user)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="club-users-mobile-list">
            {store.clubUsers.map((user) => (
              <Card
                key={user.id}
                className={`club-user-mobile-card ${
                  user.is_active ? "" : "is-inactive"
                }`}
              >
                <div className="club-user-mobile-header">
                  <div>
                    <h3>{user.full_name}</h3>
                    <p>{user.email}</p>
                  </div>
                  {renderStatus(user)}
                </div>
                <div className="club-user-role-row">
                  <span>Rol</span>
                  <strong>{getRoleLabel(user.role)}</strong>
                </div>
                {renderActions(user)}
              </Card>
            ))}
          </div>
        </>
      )}

      {createdCredentials && (
        <div
          className="club-user-modal-backdrop"
          role="presentation"
          onClick={closeCredentials}
        >
          <section
            className="club-user-credentials-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="club-user-credentials-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="club-user-modal-heading">
              <div>
                <span className="status-badge status-success">Creado</span>
                <h2 id="club-user-credentials-title">
                  Guarda las credenciales
                </h2>
              </div>
              <button
                type="button"
                className="club-user-modal-close"
                aria-label="Cerrar"
                onClick={closeCredentials}
              >
                ×
              </button>
            </div>

            <p className="club-user-credentials-warning">
              Esta contraseña solo se mostrará ahora. El usuario deberá
              cambiarla en su primer acceso.
            </p>

            <dl className="club-user-credentials-list">
              <div>
                <dt>Nombre</dt>
                <dd>{createdCredentials.fullName}</dd>
              </div>
              <div>
                <dt>Rol</dt>
                <dd>{getRoleLabel(createdCredentials.role)}</dd>
              </div>
              <div>
                <dt>Correo</dt>
                <dd>
                  <span>{createdCredentials.email}</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(createdCredentials.email)}
                  >
                    Copiar
                  </button>
                </dd>
              </div>
              <div>
                <dt>Contraseña temporal</dt>
                <dd>
                  <code>{createdCredentials.password}</code>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(createdCredentials.password)}
                  >
                    Copiar
                  </button>
                </dd>
              </div>
            </dl>

            <div className="club-user-credentials-actions">
              <Button type="button" onClick={copyCredentials}>
                Copiar credenciales
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={closeCredentials}
              >
                Ya las guardé
              </Button>
            </div>
          </section>
        </div>
      )}
    </>
  );
};
