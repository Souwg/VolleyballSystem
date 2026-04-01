import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { AuthLayout } from "../../component/authLayout";
import {
  validateClubLocation,
  validateTeamName,
  validatePlayer,
} from "../../utils/validators";

import { errorMessages } from "../../utils/errorMessages";

import { StepIndicator } from "../../component/ui/stepIndicator";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";

export const Onboarding = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [location, setLocation] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [number, setNumber] = useState("");
  const [sex, setSex] = useState("");
  const [teamName, setTeamName] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [errors, setErrors] = useState({});
  const [savingClub, setSavingClub] = useState(false);
  const [creatingTeam, setCreatingTeam] = useState(false);
  const [creatingPlayer, setCreatingPlayer] = useState(false);

  useEffect(() => {
    actions.getOnboardingStatus();
    actions.getTeams();
  }, []);

  const step = store.onboardingStep;

  const handleSaveClub = async (e) => {
    e.preventDefault();
    if (savingClub) return;
    setErrors({});

    const newErrors = validateClubLocation(location);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSavingClub(true);

    const result = await actions.updateClub(location.trim());

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setSavingClub(false);
  };

  const handleCreateTeam = async (e) => {
    e.preventDefault();
    if (creatingTeam) return;
    setErrors({});

    const newErrors = validateTeamName(teamName);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreatingTeam(true);

    const result = await actions.createTeam(teamName.trim());

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setCreatingTeam(false);
  };
  const handleCreatePlayer = async (e) => {
    e.preventDefault();
    if (creatingPlayer) return;
    setErrors({});

    const newErrors = validatePlayer({
      first_name: firstName,
      last_name: lastName,
      player_number: number,
      sex,
      team_id: selectedTeam,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreatingPlayer(true);

    const result = await actions.createPlayer({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      player_number: Number(number),
      sex: sex,
      team_id: selectedTeam,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setCreatingPlayer(false);
  };

  useEffect(() => {
    if (step === 4) {
      setTimeout(() => {
        navigate("/dashboard");
      }, 2000);
    }
  }, [step]);

  useEffect(() => {
    if (store.club?.location) {
      setLocation(store.club.location);
    }
  }, [store.club]);

  useEffect(() => {
    if (store.teams?.length === 1) {
      setSelectedTeam(store.teams[0].id);
    }
  }, [store.teams]);

  const getContent = () => {
    switch (step) {
      case 1:
        return {
          title: "Configuración de tu club",
          subtitle: "Vamos a dejar todo listo para comenzar",
          form: (
            <form className="auth-form" onSubmit={handleSaveClub}>
              <p className="onboarding-greeting">
                Bienvenido a <strong>{store.club?.name || "tu club"}</strong> 👋
              </p>
              <Input
                type="text"
                value={store.club?.name || ""}
                disabled
                className="input-readonly"
              />
              <Input
                type="text"
                placeholder="Ubicación del club"
                value={location}
                className={errors.LOCATION_REQUIRED ? "input-error" : ""}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setErrors((prev) => ({
                    ...prev,
                    LOCATION_REQUIRED: false,
                  }));
                }}
              />

              {errors.LOCATION_REQUIRED && (
                <p className="form-error">{errorMessages.LOCATION_REQUIRED}</p>
              )}

              <Button type="submit" disabled={savingClub}>
                {savingClub ? "Guardando..." : "Continuar"}
              </Button>
            </form>
          ),
        };

      case 2:
        return {
          title: "Crea tu primera categoría",
          subtitle: "Aquí comienza la organización de tu club",
          form: (
            <form className="auth-form" onSubmit={handleCreateTeam}>
              <Input
                type="text"
                placeholder="Nombre de la categoría"
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
                <p className="form-error">
                  {errorMessages.TEAM_ALREADY_EXISTS}
                </p>
              )}
              <Button type="submit" disabled={creatingTeam}>
                {creatingTeam ? "Creando..." : "Continuar"}
              </Button>
            </form>
          ),
        };

      case 3:
        return {
          title: "Agrega tu primer jugador",
          subtitle: "Empieza a construir tu equipo",
          form: (
            <form className="auth-form" onSubmit={handleCreatePlayer}>
              <div>
                <Input
                  type="text"
                  placeholder="Nombre"
                  value={firstName}
                  className={errors.FIRST_NAME_REQUIRED ? "input-error" : ""}
                  onChange={(e) => {
                    setFirstName(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      FIRST_NAME_REQUIRED: false,
                    }));
                  }}
                />

                {errors.FIRST_NAME_REQUIRED && (
                  <p className="form-error">
                    {errorMessages.FIRST_NAME_REQUIRED}
                  </p>
                )}
              </div>
              <div>
                <Input
                  type="text"
                  placeholder="Apellido"
                  value={lastName}
                  className={errors.LAST_NAME_REQUIRED ? "input-error" : ""}
                  onChange={(e) => {
                    setLastName(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      LAST_NAME_REQUIRED: false,
                    }));
                  }}
                />

                {errors.LAST_NAME_REQUIRED && (
                  <p className="form-error">
                    {errorMessages.LAST_NAME_REQUIRED}
                  </p>
                )}
              </div>
              <div>
                <Input
                  type="number"
                  placeholder="Número del jugador"
                  value={number}
                  className={
                    errors.PLAYER_NUMBER_REQUIRED ||
                    errors.INVALID_PLAYER_NUMBER ||
                    errors.PLAYER_NUMBER_DUPLICATED
                      ? "input-error"
                      : ""
                  }
                  onChange={(e) => {
                    setNumber(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      PLAYER_NUMBER_REQUIRED: false,
                      INVALID_PLAYER_NUMBER: false,
                      PLAYER_NUMBER_DUPLICATED: false,
                    }));
                  }}
                />
                {errors.PLAYER_NUMBER_REQUIRED && (
                  <p className="form-error">
                    {errorMessages.PLAYER_NUMBER_REQUIRED}
                  </p>
                )}
                {errors.INVALID_PLAYER_NUMBER && (
                  <p className="form-error">
                    {errorMessages.INVALID_PLAYER_NUMBER}
                  </p>
                )}

                {errors.PLAYER_NUMBER_DUPLICATED && (
                  <p className="form-error">
                    {errorMessages.PLAYER_NUMBER_DUPLICATED}
                  </p>
                )}
              </div>
              <div>
                <select
                  className={`select ${
                    errors.INVALID_SEX || errors.SEX_REQUIRED
                      ? "input-error"
                      : ""
                  }`}
                  value={sex}
                  onChange={(e) => {
                    setSex(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      INVALID_SEX: false,
                      SEX_REQUIRED: false,
                    }));
                  }}
                >
                  <option value="">Sexo</option>
                  <option value="male">Masculino</option>
                  <option value="female">Femenino</option>
                </select>
                {errors.SEX_REQUIRED && (
                  <p className="form-error">{errorMessages.SEX_REQUIRED}</p>
                )}

                {errors.INVALID_SEX && (
                  <p className="form-error">{errorMessages.INVALID_SEX}</p>
                )}
              </div>
              <div>
                <select
                  className={`select ${
                    errors.TEAM_ID_REQUIRED ? "input-error" : ""
                  }`}
                  value={selectedTeam}
                  onChange={(e) => {
                    setSelectedTeam(e.target.value);
                    setErrors((prev) => ({
                      ...prev,
                      TEAM_ID_REQUIRED: false,
                    }));
                  }}
                >
                  <option value="">Selecciona una categoría</option>
                  {store.teams?.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
                {errors.TEAM_ID_REQUIRED && (
                  <p className="form-error">{errorMessages.TEAM_ID_REQUIRED}</p>
                )}
              </div>
              <Button type="submit" disabled={creatingPlayer}>
                {creatingPlayer ? "Creando..." : "Finalizar configuración"}
              </Button>
            </form>
          ),
        };

      case 4:
        return {
          title: "Todo listo 🚀",
          subtitle: "Tu club ya está configurado",
          form: (
            <div className="onboarding-success">
              <div className="onboarding-success-icon">🎉</div>
              <h3>¡Listo para comenzar!</h3>
              <p>Tu club está preparado para empezar a trabajar.</p>
              <span>Redirigiendo al panel...</span>
            </div>
          ),
        };

      default:
        return {};
    }
  };

  const content = getContent();

  return (
    <AuthLayout title={content.title} subtitle={content.subtitle}>
      <StepIndicator step={step} total={4} />
      <p className="onboarding-progress-label">
        {step === 1 && "Configurando tu club"}
        {step === 2 && "Creando tu primera categoría"}
        {step === 3 && "Agregando jugador"}
        {step === 4 && "Todo listo"}
      </p>
      {content.form}
    </AuthLayout>
  );
};
