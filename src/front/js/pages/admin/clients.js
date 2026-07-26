import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { Input } from "../../component/ui/input";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { PageHeader } from "../../component/ui/pageHeader";
import { FormField } from "../../component/ui/formField";

import { useToast } from "../../../../context/toastContext";
import { validateClient } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

import "../../../styles/clients.css";

export const Clients = () => {
  const { store, actions } = useContext(Context);
  const { showToast } = useToast();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [clubName, setClubName] = useState("");

  const [clubState, setClubState] = useState("");
  const [createdCredentials, setCreatedCredentials] = useState(null);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    actions.getAdminClients();
  }, []);

  const createClient = async (e) => {
    e.preventDefault();

    if (loading) return;

    const newErrors = validateClient({
      full_name: fullName,
      email,
      club_name: clubName,
      state: clubState,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.createClient({
      full_name: fullName.trim(),
      email: email.trim(),
      club_name: clubName.trim(),
      state: clubState.trim(),
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }

    const credentials = result.data.credentials;

    setFullName("");
    setEmail("");
    setClubName("");
    setClubState("");

    setCreatedCredentials({
      email: credentials.email,
      password: credentials.temporary_password,
      emailSent: result.data.email_sent,
      emailWarning: result.data.email_warning,
    });

    setTimeout(() => {
      setCreatedCredentials(null);
    }, 10000);

    setLoading(false);
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Copiado al portapapeles", "success");
    } catch (err) {
      showToast("No se pudo copiar", "error");
    }
  };

  const handleDeactivate = async (client) => {
    const confirmed = window.confirm(
      `¿Seguro que deseas desactivar a ${client.full_name}?`,
    );

    if (!confirmed) return;

    await actions.toggleClientStatus(client.id, "deactivate");
  };

  return (
    <>
      {createdCredentials && (
        <div className="card success-card">
          <h3>✅ Cliente creado correctamente</h3>

          {createdCredentials.emailSent ? (
            <p className="text-muted">
              El correo de bienvenida fue enviado automáticamente al cliente.
            </p>
          ) : (
            <p className="text-muted">
              {createdCredentials.emailWarning ||
                "No se pudo enviar el correo. Comparte las credenciales manualmente."}
            </p>
          )}

          <div className="credentials-box">
            <div className="credential-item">
              <span>Email</span>
              <div className="credential-value">
                {createdCredentials.email}
                <button
                  onClick={() => copyToClipboard(createdCredentials.email)}
                >
                  Copiar
                </button>
              </div>
            </div>

            <div className="credential-item">
              <span>Password temporal</span>
              <div className="credential-value">
                <code>{createdCredentials.password}</code>
                <button
                  onClick={() => copyToClipboard(createdCredentials.password)}
                >
                  Copiar
                </button>
              </div>
            </div>
          </div>

          <div style={{ marginTop: "12px" }}>
            <Button
              onClick={() =>
                copyToClipboard(
                  `¡Bienvenido a SportFlow!

                    Tu cuenta ya está lista.

                    Correo: ${createdCredentials.email}
                    Contraseña temporal: ${createdCredentials.password}

                    Ingresa en:
                    https://sportflow.club/login

                    En tu primer acceso deberás crear una nueva contraseña.`,
                )
              }
            >
              Copiar todo
            </Button>
          </div>
        </div>
      )}

      <PageHeader
        title="Clientes"
        subtitle="Registra clubes y asigna sus datos principales."
      />
      <Card>
        <form className="form" onSubmit={createClient}>
          <FormField
            label="Nombre completo"
            error={
              errors.FULL_NAME_REQUIRED
                ? errorMessages.FULL_NAME_REQUIRED
                : null
            }
          >
            <Input
              placeholder="Ej: Ana Martínez"
              value={fullName}
              className={errors.FULL_NAME_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setFullName(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  FULL_NAME_REQUIRED: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Correo electrónico"
            error={
              errors.EMAIL_REQUIRED
                ? errorMessages.EMAIL_REQUIRED
                : errors.INVALID_EMAIL
                ? errorMessages.INVALID_EMAIL
                : errors.CLIENT_ALREADY_EXISTS
                ? errorMessages.CLIENT_ALREADY_EXISTS
                : null
            }
          >
            <Input
              placeholder="Ej: cliente@email.com"
              value={email}
              className={
                errors.CLIENT_ALREADY_EXISTS ||
                errors.EMAIL_REQUIRED ||
                errors.INVALID_EMAIL
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setEmail(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CLIENT_ALREADY_EXISTS: false,
                  EMAIL_REQUIRED: false,
                  INVALID_EMAIL: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Nombre del club"
            error={
              errors.CLUB_NAME_REQUIRED
                ? errorMessages.CLUB_NAME_REQUIRED
                : null
            }
          >
            <Input
              placeholder="Ej: Las Compotitas"
              value={clubName}
              className={errors.CLUB_NAME_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setClubName(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CLUB_NAME_REQUIRED: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Estado"
            error={errors.STATE_REQUIRED ? errorMessages.STATE_REQUIRED : null}
          >
            <Input
              placeholder="Ej: Aragua"
              value={clubState}
              className={errors.STATE_REQUIRED ? "input-error" : ""}
              onChange={(e) => {
                setClubState(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  STATE_REQUIRED: false,
                }));
              }}
            />
          </FormField>

          <div className="form-actions">
            <Button disabled={loading}>
              {loading ? "Creando..." : "Crear cliente"}
            </Button>
          </div>
        </form>
      </Card>

      <div className="clients-grid">
        {store.adminClients.map((client) => (
          <Card key={client.id}>
            <h5>{client.full_name}</h5>
            <p>{client.email}</p>
            <p>{client.is_active ? "🟢 Activo" : "🔴 Inactivo"}</p>

            {client.is_active ? (
              <Button onClick={() => handleDeactivate(client)}>
                Desactivar
              </Button>
            ) : (
              <Button
                onClick={() =>
                  actions.toggleClientStatus(client.id, "activate")
                }
              >
                Activar
              </Button>
            )}
          </Card>
        ))}
      </div>
    </>
  );
};
