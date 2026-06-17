import React, { useEffect, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { AuthLayout } from "../../component/authLayout";
import {
  validateClubLocation,
  validateCategory,
  validateTeam,
  validatePlayerProfile,
  validatePlayerAssignment,
} from "../../utils/validators";

import { errorMessages } from "../../utils/errorMessages";
import { getAssetUrl } from "../../utils/getAssetUrl";

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
  const [clubState, setClubState] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [clubImageFile, setClubImageFile] = useState(null);
  const [clubImagePreview, setClubImagePreview] = useState("");
  const [uploadingImage, setUploadingImage] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [number, setNumber] = useState("");
  const [sex, setSex] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categoryDescription, setCategoryDescription] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [teamName, setTeamName] = useState("");
  const [teamGender, setTeamGender] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [errors, setErrors] = useState({});
  const [savingClub, setSavingClub] = useState(false);
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [creatingTeam, setCreatingTeam] = useState(false);
  const [creatingPlayer, setCreatingPlayer] = useState(false);

  useEffect(() => {
    actions.getOnboardingStatus();
    actions.getCategories();
    actions.getTeams();
  }, []);

  useEffect(() => {
    if (store.categories?.length === 1) {
      setSelectedCategory(store.categories[0].id);
    }
  }, [store.categories]);

  const step = store.onboardingStep;

  useEffect(() => {
    if (step !== 5) return;

    const timeout = setTimeout(() => {
      navigate("/dashboard");
    }, 1800);

    return () => clearTimeout(timeout);
  }, [step, navigate]);

  const handleSaveClub = async (e) => {
    e.preventDefault();

    if (savingClub || uploadingImage) return;

    setErrors({});

    const newErrors = validateClubLocation(location);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSavingClub(true);

    let finalImageUrl = imageUrl.trim();

    if (clubImageFile) {
      setUploadingImage(true);

      const uploadResult = await actions.uploadClubImage(clubImageFile);

      setUploadingImage(false);

      if (!uploadResult?.ok) {
        setErrors({ [uploadResult.code]: true });
        setSavingClub(false);
        return;
      }

      finalImageUrl = uploadResult.data.image_url;
    }

    const result = await actions.updateClub({
      location: location.trim(),
      image_url: finalImageUrl,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setSavingClub(false);
      return;
    }

    await actions.getOnboardingStatus();

    setSavingClub(false);
  };

  const selectedTeamData = store.teams?.find((t) => t.id === selectedTeam);

  const selectedCategoryData = store.categories?.find(
    (category) => category.id === selectedCategory,
  );

  const handleCreateCategory = async (e) => {
    e.preventDefault();

    if (creatingCategory) return;

    setErrors({});

    const newErrors = validateCategory({
      name: categoryName,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setCreatingCategory(true);

    const result = await actions.createCategory({
      name: categoryName.trim(),
      description: categoryDescription.trim(),
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setCreatingCategory(false);
      return;
    }

    setCategoryName("");
    setCategoryDescription("");

    await actions.getCategories();
    await actions.getOnboardingStatus();

    setCreatingCategory(false);
  };

  const handleCreateTeam = async (e) => {
    e.preventDefault();

    if (creatingTeam) return;

    setErrors({});

    if (!selectedCategory) {
      setErrors({ CATEGORY_ID_REQUIRED: true });
      return;
    }

    const newErrors = validateTeam({
      name: teamName,
      gender: teamGender,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setCreatingTeam(true);

    const result = await actions.createTeamInCategory(selectedCategory, {
      name: teamName.trim(),
      gender: teamGender,
    });

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setCreatingTeam(false);
      return;
    }

    setTeamName("");
    setTeamGender("");

    await actions.getTeams();
    await actions.getOnboardingStatus();

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
      setCreatingPlayer(false);
      return;
    }

    setFirstName("");
    setLastName("");
    setNumber("");
    setSex("");

    await actions.getOnboardingStatus();

    setCreatingPlayer(false);
  };

  useEffect(() => {
    if (store.club) {
      setLocation(store.club.location?.trim() || "");
      setClubState(store.club.state?.trim() || "");
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
              <FormField
                label={
                  <span className="onboarding-label-with-icon">
                    <FaRegHandPaper className="onboarding-greeting-icon" />
                    Este es tu club
                  </span>
                }
              >
                <Input
                  type="text"
                  value={store.club?.name || ""}
                  disabled
                  className="input-readonly"
                />
              </FormField>
              <FormField label="Estado">
                <Input
                  type="text"
                  value={clubState || "Sin definir"}
                  disabled
                  className="input-readonly"
                />
              </FormField>
              <FormField
                label="Ciudad"
                error={
                  errors.LOCATION_REQUIRED
                    ? errorMessages.LOCATION_REQUIRED
                    : null
                }
              >
                <Input
                  type="text"
                  placeholder="Ej: Cagua, Caracas, Valencia..."
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

              <FormField label="Escudo del club">
                <div className="club-image-picker">
                  <div className="club-image-preview">
                    {clubImagePreview || imageUrl ? (
                      <img
                        src={clubImagePreview || getAssetUrl(imageUrl)}
                        alt="Escudo del club"
                      />
                    ) : (
                      <span>
                        {(store.club?.name || "Club")
                          .split(" ")
                          .filter(Boolean)
                          .slice(0, 2)
                          .map((word) => word.charAt(0))
                          .join("")
                          .toUpperCase()}
                      </span>
                    )}
                  </div>

                  <div className="club-image-actions">
                    <label className="button button-secondary club-image-button">
                      Subir imagen
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/jpg,image/webp"
                        hidden
                        onChange={(e) => {
                          const file = e.target.files?.[0];

                          if (!file) return;

                          setClubImageFile(file);
                          setClubImagePreview(URL.createObjectURL(file));
                          setErrors((prev) => ({
                            ...prev,
                            IMAGE_TOO_LARGE: false,
                            INVALID_IMAGE_FORMAT: false,
                            IMAGE_REQUIRED: false,
                          }));
                        }}
                      />
                    </label>

                    <small className="form-helper">
                      Opcional. Puedes subir un escudo o avatar desde tu
                      galería.
                    </small>
                  </div>
                </div>
              </FormField>
              {errors.IMAGE_TOO_LARGE && (
                <p className="form-error">{errorMessages.IMAGE_TOO_LARGE}</p>
              )}

              {errors.INVALID_IMAGE_FORMAT && (
                <p className="form-error">
                  {errorMessages.INVALID_IMAGE_FORMAT}
                </p>
              )}

              {errors.IMAGE_REQUIRED && (
                <p className="form-error">{errorMessages.IMAGE_REQUIRED}</p>
              )}

              <Button type="submit" disabled={savingClub || uploadingImage}>
                {savingClub || uploadingImage ? "Guardando..." : "Continuar"}
              </Button>
            </form>
          ),
        };

      case 2:
        return {
          title: "Crea tu primera categoría",
          subtitle: "Organiza tu club por edad, etapa o nivel deportivo",
          form: (
            <form className="auth-form" onSubmit={handleCreateCategory}>
              <FormField
                label="Nombre de la categoría"
                error={
                  errors.CATEGORY_NAME_REQUIRED
                    ? "El nombre de la categoría es obligatorio"
                    : errors.CATEGORY_ALREADY_EXISTS
                    ? "Ya existe una categoría con ese nombre"
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

              <Button type="submit" disabled={creatingCategory}>
                {creatingCategory ? "Creando..." : "Continuar"}
              </Button>
            </form>
          ),
        };

      case 3:
        return {
          title: "Crea tu primer equipo",
          subtitle:
            "Este será el grupo donde agregarás deportistas y entrenamientos",
          form: (
            <form className="auth-form" onSubmit={handleCreateTeam}>
              {store.categories?.length > 1 && (
                <FormField
                  label="Categoría"
                  error={
                    errors.CATEGORY_ID_REQUIRED
                      ? "Selecciona una categoría"
                      : null
                  }
                >
                  <Select
                    className={errors.CATEGORY_ID_REQUIRED ? "input-error" : ""}
                    value={selectedCategory}
                    onChange={(e) => {
                      setSelectedCategory(e.target.value);
                      setErrors((prev) => ({
                        ...prev,
                        CATEGORY_ID_REQUIRED: false,
                      }));
                    }}
                  >
                    <option value="">Selecciona una categoría</option>
                    {store.categories?.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </Select>
                </FormField>
              )}
              {store.categories?.length === 1 && selectedCategoryData && (
                <div className="onboarding-context-card">
                  <span>Este equipo se creará dentro de la categoría</span>
                  <strong>{selectedCategoryData.name}</strong>
                </div>
              )}
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

      case 4:
        return {
          title: "Agrega tu primer deportista",
          subtitle: "Empieza a construir el roster de tu equipo",
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
                label="Número en el equipo"
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
                label="Equipo"
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
                  <option value="">Selecciona un equipo</option>
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
              {errors.PLAYER_GENDER_MISMATCH && (
                <p className="form-error">
                  {errorMessages.PLAYER_GENDER_MISMATCH}
                </p>
              )}

              <Button type="submit" disabled={creatingPlayer}>
                {creatingPlayer ? "Creando..." : "Finalizar configuración"}
              </Button>
            </form>
          ),
        };

      case 5:
        return {
          title: "Todo listo",
          subtitle: "Tu club ya está configurado",
          form: (
            <div className="onboarding-success">
              <div className="onboarding-success-icon">✓</div>

              <div className="onboarding-success-content">
                <h3>Listo para comenzar</h3>
                <p>
                  Ya puedes gestionar categorías, equipos, deportistas,
                  entrenamientos y partidos desde tu panel.
                </p>
              </div>

              <div className="onboarding-success-summary">
                <div>
                  <span>Club</span>
                  <strong>{store.club?.name || "Configurado"}</strong>
                </div>

                <div>
                  <span>Categorías</span>
                  <strong>{store.categories?.length || 1}</strong>
                </div>

                <div>
                  <span>Equipos</span>
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
      variant={
        step === 5 || step === 2 || step === 3 || step === 1 ? "center" : "top"
      }
      title={content.title}
      subtitle={content.subtitle}
    >
      <StepIndicator step={step} total={5} />
      <p className="onboarding-progress-label">
        {step === 1 && "Configurando tu club"}
        {step === 2 && "Creando tu primera categoría"}
        {step === 3 && "Creando tu primer equipo"}
        {step === 4 && "Agregando tu primer deportista"}
      </p>
      {content.form}
    </AuthLayout>
  );
};
