import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { AuthLayout } from "../../component/authLayout";
import {
  validateClubLocation,
  validateTeam,
  validatePlayerProfile,
  validatePlayerAssignment,
} from "../../utils/validators";

import { errorMessages } from "../../utils/errorMessages";

import { StepIndicator } from "../../component/ui/stepIndicator";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { FaRegHandPaper } from "react-icons/fa";
import "../../../styles/onboarding.css";

export const Onboarding = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [location, setLocation] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [number, setNumber] = useState("");
  const [sex, setSex] = useState("");
  const [teamName, setTeamName] = useState("");
  const [teamGender, setTeamGender] = useState("");
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

  useEffect(() => {
    if (step !== 4) return;

    const timeout = setTimeout(() => {
      navigate("/dashboard");
    }, 1800);

    return () => clearTimeout(timeout);
  }, [step, navigate]);

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

    const result = await actions.updateClub({
      location: location.trim(),
      image_url: imageUrl.trim(),
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setSavingClub(false);
  };

  const selectedTeamData = store.teams?.find((t) => t.id === selectedTeam);

  const handleCreateTeam = async (e) => {
    e.preventDefault();
    if (creatingTeam) return;
    setErrors({});

    const newErrors = validateTeam({
      name: teamName,
      gender: teamGender,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreatingTeam(true);

    const result = await actions.createTeam({
      name: teamName.trim(),
      gender: teamGender,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setCreatingTeam(false);
  };
  const handleCreatePlayer = async (e) => {
    e.preventDefault();
    if (creatingPlayer) return;

    setErrors({});

    const profileErrors = validatePlayerProfile({
      first_name: firstName,
      last_name: lastName,
      sex,
    });

    const assignmentErrors = validatePlayerAssignment({
      team_id: selectedTeam,
      player_number: number,
    });

    const newErrors = {
      ...profileErrors,
      ...assignmentErrors,
    };

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreatingPlayer(true);

    const result = await actions.createPlayer({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      sex,
      team_id: selectedTeam,
      player_number: Number(number),
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
    }

    setCreatingPlayer(false);
  };

  useEffect(() => {
    if (store.club) {
      setLocation(store.club.location?.trim() || "");
      setImageUrl(store.club.image_url?.trim() || "");
    }
  }, [store.club]);

  useEffect(() => {
    if (store.teams?.length === 1) {
      setSelectedTeam(store.teams[0].id);
    }
  }, [store.teams]);

  useEffect(() => {
    if (!selectedTeamData) return;

    if (selectedTeamData.gender === "female") {
      setSex("female");
    }

    if (selectedTeamData.gender === "male") {
      setSex("male");
    }

    if (selectedTeamData.gender === "mixed") {
      setSex("");
    }
  }, [selectedTeamData]);

  const getContent = () => {
    switch (step) {
      case 1:
        return {
          title: "Configuración de tu club",
          subtitle: "Vamos a dejar todo listo para comenzar",
          form: (
            <form className="auth-form" onSubmit={handleSaveClub}>
              <p className="onboarding-greeting">
                <span>
                  Bienvenido a <strong>{store.club?.name || "tu club"}</strong>
                </span>

                <FaRegHandPaper className="onboarding-greeting-icon" />
              </p>
              <FormField label="Nombre del club">
                <Input
                  type="text"
                  value={store.club?.name || ""}
                  disabled
                  className="input-readonly"
                />
              </FormField>
              <FormField
                label="Ubicación del club"
                error={
                  errors.LOCATION_REQUIRED
                    ? errorMessages.LOCATION_REQUIRED
                    : null
                }
              >
                <Input
                  type="text"
                  placeholder="Ej: Caracas, Maracay..."
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
              </FormField>

              <FormField
                label="Escudo o avatar del club"
                helper="Opcional. Pega una URL de imagen para personalizar tu panel."
              >
                <Input
                  type="text"
                  placeholder="Ej: https://..."
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                />
              </FormField>

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
              <FormField
                label="Nombre de la categoría"
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
                  placeholder="Ej: Iniciación, Juvenil, Superior..."
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
                label="Género"
                error={
                  errors.INVALID_TEAM_GENDER
                    ? errorMessages.INVALID_TEAM_GENDER
                    : null
                }
              >
                <Select
                  className={errors.INVALID_TEAM_GENDER ? "input-error" : ""}
                  value={teamGender}
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
              <Button type="submit" disabled={creatingTeam}>
                {creatingTeam ? "Creando..." : "Continuar"}
              </Button>
            </form>
          ),
        };

      case 3:
        return {
          title: "Agrega tu primer deportista",
          subtitle: "Empieza a construir el roster de tu club",
          form: (
            <form className="auth-form" onSubmit={handleCreatePlayer}>
              <FormField
                label="Nombre"
                error={
                  errors.FIRST_NAME_REQUIRED
                    ? errorMessages.FIRST_NAME_REQUIRED
                    : null
                }
              >
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
              </FormField>
              <FormField
                label="Apellido"
                error={
                  errors.LAST_NAME_REQUIRED
                    ? errorMessages.LAST_NAME_REQUIRED
                    : null
                }
              >
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
              </FormField>

              <FormField
                label="Número en la categoría"
                error={
                  errors.PLAYER_NUMBER_REQUIRED
                    ? errorMessages.PLAYER_NUMBER_REQUIRED
                    : errors.INVALID_PLAYER_NUMBER
                    ? errorMessages.INVALID_PLAYER_NUMBER
                    : errors.PLAYER_NUMBER_DUPLICATED
                    ? errorMessages.PLAYER_NUMBER_DUPLICATED
                    : null
                }
              >
                <Input
                  type="number"
                  placeholder="Ej: 10"
                  value={number}
                  className={
                    errors.PLAYER_NUMBER_REQUIRED ||
                    errors.INVALID_PLAYER_NUMBER ||
                    errors.PLAYER_NUMBER_DUPLICATED
                      ? "input-error"
                      : ""
                  }
                  onChange={(e) => {
                    const value = e.target.value;

                    if (value === "") {
                      setNumber("");
                      setErrors((prev) => ({
                        ...prev,
                        PLAYER_NUMBER_REQUIRED: false,
                        INVALID_PLAYER_NUMBER: false,
                        PLAYER_NUMBER_DUPLICATED: false,
                      }));
                      return;
                    }

                    if (value.length > 2) return;
                    if (Number(value) <= 0) return;

                    setNumber(value);

                    setErrors((prev) => ({
                      ...prev,
                      PLAYER_NUMBER_REQUIRED: false,
                      INVALID_PLAYER_NUMBER: false,
                      PLAYER_NUMBER_DUPLICATED: false,
                    }));
                  }}
                />
              </FormField>

              {selectedTeamData?.gender === "mixed" && (
                <FormField
                  label="Sexo"
                  error={
                    errors.SEX_REQUIRED
                      ? errorMessages.SEX_REQUIRED
                      : errors.INVALID_SEX
                      ? errorMessages.INVALID_SEX
                      : null
                  }
                >
                  <Select
                    className={
                      errors.INVALID_SEX || errors.SEX_REQUIRED
                        ? "input-error"
                        : ""
                    }
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
                    <option value="">Selecciona sexo</option>
                    <option value="male">Masculino</option>
                    <option value="female">Femenino</option>
                  </Select>
                </FormField>
              )}
              <FormField
                label="Categoría"
                error={
                  errors.TEAM_ID_REQUIRED
                    ? errorMessages.TEAM_ID_REQUIRED
                    : null
                }
              >
                <Select
                  className={errors.TEAM_ID_REQUIRED ? "input-error" : ""}
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
                      {team.name} ·{" "}
                      {team.gender === "mixed"
                        ? "Mixto"
                        : team.gender === "male"
                        ? "Masculino"
                        : "Femenino"}
                    </option>
                  ))}
                </Select>
              </FormField>
              <Button type="submit" disabled={creatingPlayer}>
                {creatingPlayer ? "Creando..." : "Finalizar configuración"}
              </Button>
            </form>
          ),
        };

      case 4:
        return {
          title: "Todo listo",
          subtitle: "Tu club ya está configurado",
          form: (
            <div className="onboarding-success">
              <div className="onboarding-success-icon">✓</div>

              <div className="onboarding-success-content">
                <h3>Listo para comenzar</h3>
                <p>
                  Ya puedes gestionar categorías, deportistas, entrenamientos y
                  partidos desde tu panel.
                </p>
              </div>

              <div className="onboarding-success-summary">
                <div>
                  <span>Club</span>
                  <strong>{store.club?.name || "Configurado"}</strong>
                </div>

                <div>
                  <span>Categorías</span>
                  <strong>{store.teams?.length || 1}</strong>
                </div>
              </div>

              <p className="onboarding-redirect-text">
                Redirigiendo al panel...
              </p>
            </div>
          ),
        };
      default:
        return {};
    }
  };

  const content = getContent();

  return (
    <AuthLayout
      variant={step === 4 || step === 2 || step === 1 ? "center" : "top"}
      title={content.title}
      subtitle={content.subtitle}
    >
      <StepIndicator step={step} total={4} />
      <p className="onboarding-progress-label">
        {step === 1 && "Configurando tu club"}
        {step === 2 && "Creando tu primera categoría"}
        {step === 3 && "Agregando tu primer deportista"}
      </p>
      {content.form}
    </AuthLayout>
  );
};
