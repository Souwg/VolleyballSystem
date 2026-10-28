import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { PageHeader } from "../../component/ui/pageHeader";
import { FormField } from "../../component/ui/formField";

import { useToast } from "../../../../context/toastContext";
import { validateClient } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";
import { getPublicLoginUrl } from "../../utils/publicUrls";

import "../../../styles/clients.css";

export const Clients = () => {
  const { store, actions } = useContext(Context);
  const { showToast } = useToast();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [clubName, setClubName] = useState("");
  const [sportId, setSportId] = useState("");
  const [sports, setSports] = useState([]);
  const [countryId, setCountryId] = useState("");
  const [countries, setCountries] = useState([]);
  const [administrativeAreaId, setAdministrativeAreaId] = useState("");
  const [administrativeAreas, setAdministrativeAreas] = useState([]);
  const [city, setCity] = useState("");
  const [timezone, setTimezone] = useState("");
  const [currencyCode, setCurrencyCode] = useState("");
  const [currencies, setCurrencies] = useState([]);
  const [loadingAreas, setLoadingAreas] = useState(false);
  const [createdCredentials, setCreatedCredentials] = useState(null);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  useEffect(() => {
    actions.getAdminClients();

    const loadSports = async () => {
      const result = await actions.getAdminSports();

      if (result?.ok) {
        setSports(result.data.sports || []);
        return;
      }

      showToast(
        result?.message || "No se pudieron cargar los deportes",
        "error",
      );
    };

    const loadCountries = async () => {
      const result = await actions.getAdminCountries();

      if (result?.ok) {
        setCountries(result.data.countries || []);
        return;
      }

      showToast(
        result?.message || "No se pudieron cargar los países",
        "error",
      );
    };

    const loadCurrencies = async () => {
      const result = await actions.getAdminCurrencies();

      if (result?.ok) {
        setCurrencies(result.data.currencies || []);
        return;
      }

      showToast(
        result?.message || "No se pudieron cargar las monedas",
        "error",
      );
    };

    loadSports();
    loadCountries();
    loadCurrencies();
  }, []);

  const handleCountryChange = async (nextCountryId) => {
    const selectedCountry = countries.find(
      (country) => country.id === nextCountryId,
    );

    setCountryId(nextCountryId);
    setAdministrativeAreaId("");
    setAdministrativeAreas([]);
    setTimezone(selectedCountry?.suggested_timezone || "");
    setErrors((prev) => ({
      ...prev,
      COUNTRY_REQUIRED: false,
      INVALID_COUNTRY: false,
      COUNTRY_NOT_AVAILABLE: false,
      ADMINISTRATIVE_AREA_REQUIRED: false,
      INVALID_ADMINISTRATIVE_AREA: false,
      ADMINISTRATIVE_AREA_NOT_AVAILABLE: false,
      AREA_COUNTRY_MISMATCH: false,
      TIMEZONE_REQUIRED: false,
      INVALID_TIMEZONE: false,
    }));

    if (!nextCountryId) return;

    setLoadingAreas(true);
    const result = await actions.getAdminAreas(nextCountryId);
    setLoadingAreas(false);

    if (result?.ok) {
      setAdministrativeAreas(result.data.areas || []);
      return;
    }

    showToast(
      result?.message || "No se pudieron cargar las regiones",
      "error",
    );
  };

  const createClient = async (e) => {
    e.preventDefault();

    if (loading) return;

    const newErrors = validateClient({
      full_name: fullName,
      email,
      club_name: clubName,
      sport_id: sportId,
      country_id: countryId,
      administrative_area_id: administrativeAreaId,
      city,
      timezone,
      currency_code: currencyCode,
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
      sport_id: sportId,
      country_id: countryId,
      administrative_area_id: administrativeAreaId,
      city: city.trim(),
      timezone: timezone.trim(),
      currency_code: currencyCode,
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
    setSportId("");
    setCountryId("");
    setAdministrativeAreaId("");
    setAdministrativeAreas([]);
    setCity("");
    setTimezone("");
    setCurrencyCode("");

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

  const copyCredentials = () => {
    const loginUrl = getPublicLoginUrl();

    copyToClipboard(
      `¡Bienvenido a SportFlow!

                    Tu cuenta ya está lista.

                    Correo: ${createdCredentials.email}
                    Contraseña temporal: ${createdCredentials.password}

                    Ingresa en:
                    ${loginUrl}

                    En tu primer acceso deberás crear una nueva contraseña.`,
    );
  };

  const handleOwnerStatus = async (client) => {
    const action = client.is_active ? "deactivate" : "activate";
    const actionKey = `owner-${client.id}`;

    if (pendingAction) return;

    const confirmed = window.confirm(
      client.is_active
        ? `¿Desactivar la cuenta del propietario?\n\n${client.full_name} dejará de poder iniciar sesión.\n\nEsto NO suspende el club. Otros usuarios activos del club podrán seguir accediendo.`
        : `¿Reactivar la cuenta del propietario?\n\n${client.full_name} podrá volver a iniciar sesión si el acceso del club está activo.`,
    );

    if (!confirmed) return;

    setPendingAction(actionKey);

    try {
      await actions.toggleClientStatus(client.id, action);
    } finally {
      setPendingAction(null);
    }
  };

  const handleClubAccess = async (client) => {
    const club = client.club;

    if (!club || pendingAction) return;

    const isSuspended = club.access_status === "suspended";
    const actionKey = `club-${club.id}`;
    const confirmed = window.confirm(
      isSuspended
        ? `¿Reactivar el acceso de este club?\n\nLos usuarios activos podrán volver a iniciar sesión según sus permisos.`
        : `¿Suspender el acceso de este club?\n\nTodos los propietarios, entrenadores y usuarios administrativos del club dejarán de poder acceder a SportFlow.\n\nLos datos del club no se eliminarán.`,
    );

    if (!confirmed) return;

    setPendingAction(actionKey);

    try {
      if (isSuspended) {
        await actions.activateClub(club.id);
      } else {
        await actions.suspendClub(club.id);
      }
    } finally {
      setPendingAction(null);
    }
  };

  const getSubscriptionLabel = (status) => {
    if (status === "active") return "Activa";
    if (status === "inactive") return "Inactiva";
    return status || "No disponible";
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
            <Button onClick={copyCredentials}>
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
            label="País"
            error={
              errors.COUNTRY_REQUIRED
                ? errorMessages.COUNTRY_REQUIRED
                : errors.INVALID_COUNTRY
                ? errorMessages.INVALID_COUNTRY
                : errors.COUNTRY_NOT_AVAILABLE
                ? errorMessages.COUNTRY_NOT_AVAILABLE
                : null
            }
          >
            <Select
              value={countryId}
              className={
                errors.COUNTRY_REQUIRED ||
                errors.INVALID_COUNTRY ||
                errors.COUNTRY_NOT_AVAILABLE
                  ? "input-error"
                  : ""
              }
              onChange={(e) => handleCountryChange(e.target.value)}
            >
              <option value="">Selecciona un país</option>
              {countries.map((country) => (
                <option key={country.id} value={country.id}>
                  {country.name}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField
            label="Estado / Provincia / Región"
            error={
              errors.ADMINISTRATIVE_AREA_REQUIRED
                ? errorMessages.ADMINISTRATIVE_AREA_REQUIRED
                : errors.INVALID_ADMINISTRATIVE_AREA
                ? errorMessages.INVALID_ADMINISTRATIVE_AREA
                : errors.ADMINISTRATIVE_AREA_NOT_AVAILABLE
                ? errorMessages.ADMINISTRATIVE_AREA_NOT_AVAILABLE
                : errors.AREA_COUNTRY_MISMATCH
                ? errorMessages.AREA_COUNTRY_MISMATCH
                : null
            }
          >
            <Select
              value={administrativeAreaId}
              disabled={!countryId || loadingAreas}
              className={
                errors.ADMINISTRATIVE_AREA_REQUIRED ||
                errors.INVALID_ADMINISTRATIVE_AREA ||
                errors.ADMINISTRATIVE_AREA_NOT_AVAILABLE ||
                errors.AREA_COUNTRY_MISMATCH
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setAdministrativeAreaId(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  ADMINISTRATIVE_AREA_REQUIRED: false,
                  INVALID_ADMINISTRATIVE_AREA: false,
                  ADMINISTRATIVE_AREA_NOT_AVAILABLE: false,
                  AREA_COUNTRY_MISMATCH: false,
                }));
              }}
            >
              <option value="">
                {loadingAreas ? "Cargando..." : "Selecciona una región"}
              </option>
              {administrativeAreas.map((area) => (
                <option key={area.id} value={area.id}>
                  {area.name}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField
            label="Ciudad"
            error={
              errors.CITY_REQUIRED
                ? errorMessages.CITY_REQUIRED
                : errors.CITY_TOO_LONG
                ? errorMessages.CITY_TOO_LONG
                : null
            }
          >
            <Input
              placeholder="Ej: Cagua"
              value={city}
              maxLength={120}
              className={
                errors.CITY_REQUIRED || errors.CITY_TOO_LONG
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setCity(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CITY_REQUIRED: false,
                  CITY_TOO_LONG: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Zona horaria *"
            error={
              errors.TIMEZONE_REQUIRED
                ? errorMessages.TIMEZONE_REQUIRED
                : errors.INVALID_TIMEZONE
                ? errorMessages.INVALID_TIMEZONE
                : null
            }
          >
            <Input
              placeholder="Ej: America/Caracas"
              value={timezone}
              className={
                errors.TIMEZONE_REQUIRED || errors.INVALID_TIMEZONE
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setTimezone(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  TIMEZONE_REQUIRED: false,
                  INVALID_TIMEZONE: false,
                }));
              }}
            />
          </FormField>

          <FormField
            label="Deporte"
            error={
              errors.SPORT_REQUIRED
                ? errorMessages.SPORT_REQUIRED
                : errors.INVALID_SPORT
                ? errorMessages.INVALID_SPORT
                : errors.SPORT_NOT_AVAILABLE
                ? errorMessages.SPORT_NOT_AVAILABLE
                : null
            }
          >
            <Select
              value={sportId}
              className={
                errors.SPORT_REQUIRED ||
                errors.INVALID_SPORT ||
                errors.SPORT_NOT_AVAILABLE
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setSportId(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  SPORT_REQUIRED: false,
                  INVALID_SPORT: false,
                  SPORT_NOT_AVAILABLE: false,
                }));
              }}
            >
              <option value="">Selecciona un deporte</option>
              {sports.map((sport) => (
                <option key={sport.id} value={sport.id}>
                  {sport.name}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField
            label="Moneda *"
            error={
              errors.CURRENCY_REQUIRED
                ? errorMessages.CURRENCY_REQUIRED
                : errors.INVALID_CURRENCY
                ? errorMessages.INVALID_CURRENCY
                : null
            }
          >
            <Select
              value={currencyCode}
              className={
                errors.CURRENCY_REQUIRED || errors.INVALID_CURRENCY
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setCurrencyCode(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CURRENCY_REQUIRED: false,
                  INVALID_CURRENCY: false,
                }));
              }}
            >
              <option value="">Selecciona una moneda</option>
              {currencies.map((currency) => (
                <option key={currency.code} value={currency.code}>
                  {currency.code} — {currency.name}
                </option>
              ))}
            </Select>
          </FormField>

          <div className="form-actions">
            <Button disabled={loading}>
              {loading ? "Creando..." : "Crear cliente"}
            </Button>
          </div>
        </form>
      </Card>

      <div className="clients-grid">
        {store.adminClients.map((client) => {
          const club = client.club;
          const clubSuspended = club?.access_status === "suspended";
          const ownerPending = pendingAction === `owner-${client.id}`;
          const clubPending = pendingAction === `club-${club?.id}`;

          return (
            <Card key={client.id} className="client-admin-card">
              <div className="client-admin-heading">
                <div>
                  <span className="client-admin-eyebrow">Club</span>
                  <h5>{club?.name || "Club no disponible"}</h5>
                  <p>{client.full_name}</p>
                  <p className="client-admin-email">{client.email}</p>
                </div>

                <span
                  className={`status-badge ${
                    clubSuspended ? "status-danger" : "status-success"
                  }`}
                >
                  Club {clubSuspended ? "suspendido" : "activo"}
                </span>
              </div>

              <div className="client-status-list" aria-label="Estados del cliente">
                <div className="client-status-row">
                  <span>Deporte</span>
                  <span>{club?.sport?.name || "No disponible"}</span>
                </div>

                <div className="client-status-row">
                  <span>País</span>
                  <span>{club?.country?.name || "No clasificado"}</span>
                </div>

                <div className="client-status-row">
                  <span>Moneda</span>
                  <span>
                    {club?.currency
                      ? `${club.currency.code} — ${club.currency.name}`
                      : club?.currency_code || "No configurada"}
                  </span>
                </div>

                <div className="client-status-row">
                  <span>Estado / Provincia / Región</span>
                  <span>
                    {club?.administrative_area?.name ||
                      club?.state ||
                      "No clasificado"}
                  </span>
                </div>

                <div className="client-status-row">
                  <span>Ciudad</span>
                  <span>{club?.city || club?.location || "No registrada"}</span>
                </div>

                <div className="client-status-row">
                  <span>Acceso del Club</span>
                  <span
                    className={`status-badge ${
                      clubSuspended ? "status-danger" : "status-success"
                    }`}
                  >
                    {clubSuspended ? "Suspendido" : "Activo"}
                  </span>
                </div>

                <div className="client-status-row">
                  <span>Propietario</span>
                  <span
                    className={`status-badge ${
                      client.is_active ? "status-success" : "status-danger"
                    }`}
                  >
                    {client.is_active ? "Activo" : "Inactivo"}
                  </span>
                </div>

                <div className="client-status-row">
                  <span>Suscripción</span>
                  <span className="status-badge status-muted">
                    {getSubscriptionLabel(client.subscription_status)}
                  </span>
                </div>
              </div>

              <div className="client-admin-actions">
                <Button
                  variant={clubSuspended ? "primary" : "danger"}
                  disabled={!club || pendingAction !== null}
                  onClick={() => handleClubAccess(client)}
                >
                  {clubPending
                    ? clubSuspended
                      ? "Reactivando club..."
                      : "Suspendiendo club..."
                    : clubSuspended
                    ? "Reactivar club"
                    : "Suspender club"}
                </Button>

                <Button
                  variant={client.is_active ? "secondary" : "primary"}
                  disabled={pendingAction !== null}
                  onClick={() => handleOwnerStatus(client)}
                >
                  {ownerPending
                    ? client.is_active
                      ? "Desactivando propietario..."
                      : "Reactivando propietario..."
                    : client.is_active
                    ? "Desactivar propietario"
                    : "Reactivar propietario"}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
};
