import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { PageHeader } from "../../component/ui/pageHeader";
import { Container } from "../../component/ui/container";
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
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.createClient({
      full_name: fullName,
      email,
      club_name: clubName,
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

    setCreatedCredentials({
      email: credentials.email,
      password: credentials.temporary_password,
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

  return (
    <Container>
      {createdCredentials && (
        <div className="card success-card">
          <h3>✅ Cliente creado correctamente</h3>

          <p className="text-muted">
            Envía estas credenciales al cliente para que acceda al sistema
          </p>

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

          {/* 🔥 AQUÍ VA */}
          <div style={{ marginTop: "12px" }}>
            <Button
              onClick={() =>
                copyToClipboard(
                  `Email: ${createdCredentials.email}\nPassword: ${createdCredentials.password}`,
                )
              }
            >
              Copiar todo
            </Button>
          </div>
        </div>
      )}

      <PageHeader title="Clients" />

      <form onSubmit={createClient}>
        <div>
          <div>
            <Input
              placeholder="Full name"
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

            {errors.FULL_NAME_REQUIRED && (
              <p className="form-error">{errorMessages.FULL_NAME_REQUIRED}</p>
            )}
          </div>

          <div>
            <Input
              placeholder="Email"
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

            {errors.EMAIL_REQUIRED && (
              <p className="form-error">{errorMessages.EMAIL_REQUIRED}</p>
            )}

            {errors.CLIENT_ALREADY_EXISTS && (
              <p className="form-error">
                {errorMessages.CLIENT_ALREADY_EXISTS}
              </p>
            )}
            {errors.INVALID_EMAIL && (
              <p className="form-error">{errorMessages.INVALID_EMAIL}</p>
            )}
          </div>

          <div>
            <Input
              placeholder="Club name"
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

            {errors.CLUB_NAME_REQUIRED && (
              <p className="form-error">{errorMessages.CLUB_NAME_REQUIRED}</p>
            )}
          </div>
        </div>

        <Button disabled={loading}>
          {loading ? "Creating..." : "Create Client"}
        </Button>
      </form>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>

        <tbody>
          {store.adminClients.map((client) => {
            return (
              <tr key={client.id}>
                <td>{client.full_name}</td>

                <td>{client.email}</td>

                <td>{client.is_active ? "Active" : "Inactive"}</td>

                <td>
                  {client.is_active ? (
                    <Button
                      onClick={() =>
                        actions.toggleClientStatus(client.id, "deactivate")
                      }
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button
                      onClick={() =>
                        actions.toggleClientStatus(client.id, "activate")
                      }
                    >
                      Activate
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Container>
  );
};
