import React, { useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthLayout } from "../../component/authLayout";
import { Button } from "../../component/ui/button";
import { FormField } from "../../component/ui/formField";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { StepIndicator } from "../../component/ui/stepIndicator";
import { Context } from "../../store/appContext";
import { errorMessages } from "../../utils/errorMessages";
import {
  validateCategory,
  validatePlayerAssignment,
  validatePlayerProfile,
  validateTeam,
} from "../../utils/validators";

import "../../../styles/clubShared.css";
import "../../../styles/onboarding.css";

const TASK_LABELS = ["Categoría", "Equipo", "Deportista"];
const GENERIC_ACTION_ERROR =
  "No pudimos completar esta acción. Intenta nuevamente.";
const FIELD_ERROR_CODES = {
  category: ["CATEGORY_NAME_REQUIRED", "CATEGORY_ALREADY_EXISTS"],
  team: [
    "CATEGORY_ID_REQUIRED",
    "TEAM_NAME_REQUIRED",
    "TEAM_ALREADY_EXISTS",
    "INVALID_TEAM_GENDER",
  ],
  player: [
    "FIRST_NAME_REQUIRED",
    "LAST_NAME_REQUIRED",
    "PLAYER_NUMBER_REQUIRED",
    "INVALID_PLAYER_NUMBER",
    "PLAYER_NUMBER_DUPLICATED",
    "SEX_REQUIRED",
    "INVALID_SEX",
    "TEAM_ID_REQUIRED",
    "PLAYER_GENDER_MISMATCH",
  ],
};

const getTaskStep = (apiStep) => {
  if (apiStep >= 4) return 3;
  if (apiStep === 3) return 2;
  return 1;
};

export const Onboarding = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const titleRef = useRef(null);

  const [loadState, setLoadState] = useState("loading");
  const [categoryName, setCategoryName] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [teamName, setTeamName] = useState("");
  const [teamGender, setTeamGender] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [number, setNumber] = useState("");
  const [sex, setSex] = useState("");
  const [errors, setErrors] = useState({});
  const [generalError, setGeneralError] = useState("");
  const [retryKind, setRetryKind] = useState("");
  const [warningAction, setWarningAction] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [creatingTeam, setCreatingTeam] = useState(false);
  const [creatingPlayer, setCreatingPlayer] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [waitingForProgress, setWaitingForProgress] = useState(false);

  const taskStep = getTaskStep(store.onboardingStep);
  const showingFinal =
    store.onboardingStatus === "completed" && store.onboardingJustFinished;

  const clearActionError = () => {
    setGeneralError("");
    setRetryKind("");
  };

  const loadOnboarding = async () => {
    setLoadState("loading");
    clearActionError();
    const statusResult = await actions.getOnboardingStatus();

    if (!statusResult?.ok) {
      setLoadState("error");
      return false;
    }

    if (statusResult.data.status !== "completed") {
      const [categoriesResult, teamsResult] = await Promise.all([
        actions.getCategories(),
        actions.getTeams(),
      ]);

      if (!categoriesResult?.ok || !teamsResult?.ok) {
        setLoadState("error");
        return false;
      }
    }

    setLoadState("ready");
    return true;
  };

  useEffect(() => {
    loadOnboarding();
  }, []);

  useEffect(() => {
    if (store.categories?.length === 1 && !selectedCategory) {
      setSelectedCategory(store.categories[0].id);
    }
  }, [store.categories, selectedCategory]);

  useEffect(() => {
    if (store.teams?.length === 1 && !selectedTeam) {
      setSelectedTeam(store.teams[0].id);
    }
  }, [store.teams, selectedTeam]);

  const selectedCategoryData = store.categories?.find(
    (category) => category.id === selectedCategory,
  );
  const selectedTeamData = store.teams?.find(
    (team) => team.id === selectedTeam,
  );

  useEffect(() => {
    if (!selectedTeamData) return;
    setSex(
      ["female", "male"].includes(selectedTeamData.gender)
        ? selectedTeamData.gender
        : "",
    );
  }, [selectedTeamData]);

  useEffect(() => {
    if (loadState !== "ready") return;
    window.scrollTo(0, 0);
    titleRef.current?.focus();
  }, [taskStep, showingFinal, loadState]);

  const focusField = (ids) => {
    window.setTimeout(() => {
      const field = ids.map((id) => document.getElementById(id)).find(Boolean);
      field?.focus();
    }, 0);
  };

  const showResultError = (result, scope) => {
    if (FIELD_ERROR_CODES[scope].includes(result?.code)) {
      setErrors({ [result.code]: true });
    } else {
      setGeneralError(GENERIC_ACTION_ERROR);
    }
  };

  const syncProgress = async () => {
    setWaitingForProgress(true);
    const [statusResult, categoriesResult, teamsResult] = await Promise.all([
      actions.getOnboardingStatus(),
      actions.getCategories(),
      actions.getTeams(),
    ]);
    setWaitingForProgress(false);

    if (!statusResult?.ok || !categoriesResult?.ok || !teamsResult?.ok) {
      setGeneralError(
        "La información se guardó, pero no pudimos cargar el siguiente paso.",
      );
      setRetryKind("progress");
      return false;
    }

    clearActionError();
    return true;
  };

  const retryProgress = async () => {
    const synced = await syncProgress();
    if (synced) {
      setCategoryName("");
      setTeamName("");
      setTeamGender("");
    }
  };

  const handleCreateCategory = async (event) => {
    event.preventDefault();
    if (creatingCategory || waitingForProgress) return;
    setErrors({});
    clearActionError();
    const nextErrors = validateCategory({ name: categoryName });

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      focusField(["onboarding-category-name"]);
      return;
    }

    setCreatingCategory(true);
    const result = await actions.createCategory({ name: categoryName.trim() });
    setCreatingCategory(false);

    if (!result?.ok) {
      showResultError(result, "category");
      focusField(["onboarding-category-name"]);
      return;
    }

    setSelectedCategory(result.data.category.id);
    if (await syncProgress()) setCategoryName("");
  };

  const handleCreateTeam = async (event) => {
    event.preventDefault();
    if (creatingTeam || waitingForProgress) return;
    setErrors({});
    clearActionError();

    if (!selectedCategory) {
      setErrors({ CATEGORY_ID_REQUIRED: true });
      focusField(["onboarding-category"]);
      return;
    }

    const nextErrors = validateTeam({ name: teamName, gender: teamGender });
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      focusField(["onboarding-team-name", "onboarding-team-gender"]);
      return;
    }

    setCreatingTeam(true);
    const result = await actions.createTeamInCategory(selectedCategory, {
      name: teamName.trim(),
      gender: teamGender,
    });
    setCreatingTeam(false);

    if (!result?.ok) {
      showResultError(result, "team");
      focusField(["onboarding-team-name", "onboarding-team-gender"]);
      return;
    }

    setSelectedTeam(result.data.team.id);
    if (await syncProgress()) {
      setTeamName("");
      setTeamGender("");
    }
  };

  const finishWithFinalScreen = async () => {
    if (finishing) return false;
    setFinishing(true);
    clearActionError();
    const result = await actions.finishOnboarding();
    setFinishing(false);

    if (!result?.ok) {
      setGeneralError(GENERIC_ACTION_ERROR);
      setRetryKind("finish-final");
      return false;
    }

    setWarningAction("");
    return true;
  };

  const handleCreatePlayer = async (event) => {
    event.preventDefault();
    if (creatingPlayer || finishing) return;
    setErrors({});
    clearActionError();
    const nextErrors = {
      ...validatePlayerProfile({
        first_name: firstName,
        last_name: lastName,
        sex,
      }),
      ...validatePlayerAssignment({
        team_id: selectedTeam,
        player_number: number,
      }),
    };

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      focusField([
        "onboarding-player-first-name",
        "onboarding-player-last-name",
        "onboarding-player-number",
        "onboarding-player-sex",
        "onboarding-team",
      ]);
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
    setCreatingPlayer(false);

    if (!result?.ok) {
      showResultError(result, "player");
      focusField([
        "onboarding-player-first-name",
        "onboarding-player-last-name",
        "onboarding-player-number",
        "onboarding-player-sex",
        "onboarding-team",
      ]);
      return;
    }

    await finishWithFinalScreen();
  };

  const hasUnsavedChanges = () => {
    if (taskStep === 1) return Boolean(categoryName.trim());
    if (taskStep === 2) return Boolean(teamName.trim() || teamGender);
    return Boolean(
      firstName.trim() ||
        lastName.trim() ||
        number ||
        (selectedTeamData?.gender === "mixed" && sex),
    );
  };

  const finishAndGoToDashboard = async () => {
    if (finishing) return;
    setFinishing(true);
    clearActionError();
    const result = await actions.finishOnboarding();
    setFinishing(false);

    if (!result?.ok) {
      setGeneralError(GENERIC_ACTION_ERROR);
      setRetryKind("finish-dashboard");
      return;
    }

    actions.dismissOnboardingCompletion();
    navigate("/dashboard", { replace: true });
  };

  const requestExit = (action) => {
    clearActionError();
    if (hasUnsavedChanges()) {
      setWarningAction(action);
      return;
    }
    action === "finish-final"
      ? finishWithFinalScreen()
      : finishAndGoToDashboard();
  };

  const confirmWarning = () => {
    const action = warningAction;
    setWarningAction("");
    action === "finish-final"
      ? finishWithFinalScreen()
      : finishAndGoToDashboard();
  };

  const handleRetry = () => {
    if (retryKind === "progress") retryProgress();
    if (retryKind === "finish-final") finishWithFinalScreen();
    if (retryKind === "finish-dashboard") finishAndGoToDashboard();
  };

  const goToDashboard = () => {
    actions.dismissOnboardingCompletion();
    navigate("/dashboard", { replace: true });
  };

  if (loadState === "loading") {
    return (
      <AuthLayout
        title="Preparando tu configuración…"
        subtitle="Estamos revisando lo esencial de tu club."
      >
        <div className="onboarding-loading" role="status">
          <span className="onboarding-spinner" aria-hidden="true" />
          Preparando tu configuración…
        </div>
      </AuthLayout>
    );
  }

  if (loadState === "error") {
    return (
      <AuthLayout
        title="No pudimos preparar tu configuración"
        subtitle="Revisa tu conexión e intenta nuevamente."
      >
        <div className="onboarding-load-error" role="alert">
          <p>{GENERIC_ACTION_ERROR}</p>
          <Button type="button" onClick={loadOnboarding}>Reintentar</Button>
        </div>
      </AuthLayout>
    );
  }

  if (showingFinal) {
    return (
      <AuthLayout
        title="Tu primer equipo está listo"
        subtitle="Ya tienes la estructura esencial para comenzar en SportFlow."
        titleRef={titleRef}
        titleTabIndex="-1"
      >
        <div className="onboarding-success">
          <div className="onboarding-success-icon" aria-hidden="true">✓</div>
          <div className="onboarding-success-content">
            <h3>Todo preparado para comenzar</h3>
            <p>
              Desde el panel podrás seguir gestionando tu club y completar la
              información cuando la necesites.
            </p>
          </div>
          <Button type="button" onClick={goToDashboard}>Ir al panel</Button>
        </div>
      </AuthLayout>
    );
  }

  const titles = {
    1: {
      title: "Bienvenido a SportFlow",
      subtitle: "Vamos a preparar lo esencial de tu club.",
    },
    2: {
      title: "Crea tu primer equipo",
      subtitle: "Define el grupo donde organizarás a tus deportistas.",
    },
    3: {
      title: "Agrega tu primer deportista",
      subtitle:
        "Agrega un deportista para ver cómo queda organizado dentro de tu equipo.",
    },
  };
  const currentTitle = titles[taskStep];

  return (
    <AuthLayout
      variant={taskStep === 3 ? "top" : "center"}
      title={currentTitle.title}
      subtitle={currentTitle.subtitle}
      titleRef={titleRef}
      titleTabIndex="-1"
    >
      <StepIndicator step={taskStep} labels={TASK_LABELS} />

      {taskStep === 1 && (
        <>
          <div className="onboarding-club-summary">
            <span>3 pasos · unos minutos</span>
            <strong>{store.club?.name}</strong>
            <p>
              {[store.club?.sport?.name, store.club?.city || store.club?.location]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="onboarding-task-intro">
            <h3>Crea tu primera categoría</h3>
            <p>Una categoría agrupa equipos por edad, nivel o etapa deportiva.</p>
          </div>
          <form className="auth-form" onSubmit={handleCreateCategory} noValidate>
            <FormField
              label="Nombre de la categoría"
              htmlFor="onboarding-category-name"
              error={
                errors.CATEGORY_NAME_REQUIRED
                  ? errorMessages.CATEGORY_NAME_REQUIRED
                  : errors.CATEGORY_ALREADY_EXISTS
                  ? errorMessages.CATEGORY_ALREADY_EXISTS
                  : null
              }
              errorId="onboarding-category-name-error"
              helper="Ejemplos: Iniciación, U12, U14 o Juvenil."
            >
              <Input
                id="onboarding-category-name"
                type="text"
                value={categoryName}
                placeholder="Ej: U14"
                aria-invalid={Boolean(
                  errors.CATEGORY_NAME_REQUIRED || errors.CATEGORY_ALREADY_EXISTS,
                )}
                aria-describedby={
                  errors.CATEGORY_NAME_REQUIRED || errors.CATEGORY_ALREADY_EXISTS
                    ? "onboarding-category-name-error"
                    : undefined
                }
                className={
                  errors.CATEGORY_NAME_REQUIRED || errors.CATEGORY_ALREADY_EXISTS
                    ? "input-error"
                    : ""
                }
                onChange={(event) => {
                  setCategoryName(event.target.value);
                  setErrors({});
                  clearActionError();
                }}
              />
            </FormField>
            <Button type="submit" disabled={creatingCategory || waitingForProgress}>
              {creatingCategory || waitingForProgress
                ? "Creando..."
                : "Crear categoría"}
            </Button>
          </form>
        </>
      )}

      {taskStep === 2 && (
        <form className="auth-form" onSubmit={handleCreateTeam} noValidate>
          {store.categories?.length > 1 ? (
            <FormField
              label="Categoría"
              htmlFor="onboarding-category"
              error={
                errors.CATEGORY_ID_REQUIRED
                  ? errorMessages.CATEGORY_ID_REQUIRED
                  : null
              }
              errorId="onboarding-category-error"
            >
              <Select
                id="onboarding-category"
                value={selectedCategory}
                aria-invalid={Boolean(errors.CATEGORY_ID_REQUIRED)}
                aria-describedby={
                  errors.CATEGORY_ID_REQUIRED ? "onboarding-category-error" : undefined
                }
                className={errors.CATEGORY_ID_REQUIRED ? "input-error" : ""}
                onChange={(event) => {
                  setSelectedCategory(event.target.value);
                  setErrors({});
                }}
              >
                <option value="">Selecciona una categoría</option>
                {store.categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </Select>
            </FormField>
          ) : (
            selectedCategoryData && (
              <div className="onboarding-context-card">
                <span>Categoría</span>
                <strong>{selectedCategoryData.name}</strong>
              </div>
            )
          )}

          <FormField
            label="Nombre del equipo"
            htmlFor="onboarding-team-name"
            error={
              errors.TEAM_NAME_REQUIRED
                ? errorMessages.TEAM_NAME_REQUIRED
                : errors.TEAM_ALREADY_EXISTS
                ? errorMessages.TEAM_ALREADY_EXISTS
                : null
            }
            errorId="onboarding-team-name-error"
          >
            <Input
              id="onboarding-team-name"
              type="text"
              value={teamName}
              placeholder="Ej: U14 Femenino"
              aria-invalid={Boolean(errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS)}
              aria-describedby={
                errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                  ? "onboarding-team-name-error"
                  : undefined
              }
              className={
                errors.TEAM_NAME_REQUIRED || errors.TEAM_ALREADY_EXISTS
                  ? "input-error"
                  : ""
              }
              onChange={(event) => {
                setTeamName(event.target.value);
                setErrors((current) => ({
                  ...current,
                  TEAM_NAME_REQUIRED: false,
                  TEAM_ALREADY_EXISTS: false,
                }));
                clearActionError();
              }}
            />
          </FormField>

          <FormField
            label="Rama del equipo"
            htmlFor="onboarding-team-gender"
            error={
              errors.INVALID_TEAM_GENDER ? errorMessages.INVALID_TEAM_GENDER : null
            }
            errorId="onboarding-team-gender-error"
          >
            <Select
              id="onboarding-team-gender"
              value={teamGender}
              aria-invalid={Boolean(errors.INVALID_TEAM_GENDER)}
              aria-describedby={
                errors.INVALID_TEAM_GENDER
                  ? "onboarding-team-gender-error"
                  : undefined
              }
              className={errors.INVALID_TEAM_GENDER ? "input-error" : ""}
              onChange={(event) => {
                setTeamGender(event.target.value);
                setErrors((current) => ({
                  ...current,
                  INVALID_TEAM_GENDER: false,
                }));
                clearActionError();
              }}
            >
              <option value="">Selecciona una rama</option>
              <option value="female">Femenina</option>
              <option value="male">Masculina</option>
              <option value="mixed">Mixta</option>
            </Select>
          </FormField>
          <Button type="submit" disabled={creatingTeam || waitingForProgress}>
            {creatingTeam || waitingForProgress ? "Creando..." : "Crear equipo"}
          </Button>
        </form>
      )}

      {taskStep === 3 && (
        <>
          <div className="onboarding-recommended">
            Recomendado · puedes hacerlo después
          </div>
          <form className="auth-form" onSubmit={handleCreatePlayer} noValidate>
            <PlayerField
              id="onboarding-player-first-name"
              label="Nombre"
              value={firstName}
              errorCode="FIRST_NAME_REQUIRED"
              errors={errors}
              onChange={(value) => {
                setFirstName(value);
                setErrors((current) => ({ ...current, FIRST_NAME_REQUIRED: false }));
                clearActionError();
              }}
            />
            <PlayerField
              id="onboarding-player-last-name"
              label="Apellido"
              value={lastName}
              errorCode="LAST_NAME_REQUIRED"
              errors={errors}
              onChange={(value) => {
                setLastName(value);
                setErrors((current) => ({ ...current, LAST_NAME_REQUIRED: false }));
                clearActionError();
              }}
            />
            <FormField
              label="Número en el equipo"
              htmlFor="onboarding-player-number"
              error={
                errors.PLAYER_NUMBER_REQUIRED
                  ? errorMessages.PLAYER_NUMBER_REQUIRED
                  : errors.INVALID_PLAYER_NUMBER
                  ? errorMessages.INVALID_PLAYER_NUMBER
                  : errors.PLAYER_NUMBER_DUPLICATED
                  ? errorMessages.PLAYER_NUMBER_DUPLICATED
                  : null
              }
              errorId="onboarding-player-number-error"
            >
              <Input
                id="onboarding-player-number"
                type="number"
                min="1"
                max="99"
                value={number}
                aria-invalid={Boolean(
                  errors.PLAYER_NUMBER_REQUIRED ||
                    errors.INVALID_PLAYER_NUMBER ||
                    errors.PLAYER_NUMBER_DUPLICATED,
                )}
                aria-describedby={
                  errors.PLAYER_NUMBER_REQUIRED ||
                  errors.INVALID_PLAYER_NUMBER ||
                  errors.PLAYER_NUMBER_DUPLICATED
                    ? "onboarding-player-number-error"
                    : undefined
                }
                className={
                  errors.PLAYER_NUMBER_REQUIRED ||
                  errors.INVALID_PLAYER_NUMBER ||
                  errors.PLAYER_NUMBER_DUPLICATED
                    ? "input-error"
                    : ""
                }
                onChange={(event) => {
                  setNumber(event.target.value);
                  setErrors((current) => ({
                    ...current,
                    PLAYER_NUMBER_REQUIRED: false,
                    INVALID_PLAYER_NUMBER: false,
                    PLAYER_NUMBER_DUPLICATED: false,
                  }));
                  clearActionError();
                }}
              />
            </FormField>

            {selectedTeamData?.gender === "mixed" && (
              <FormField
                label="Sexo"
                htmlFor="onboarding-player-sex"
                error={
                  errors.SEX_REQUIRED
                    ? errorMessages.SEX_REQUIRED
                    : errors.INVALID_SEX
                    ? errorMessages.INVALID_SEX
                    : null
                }
                errorId="onboarding-player-sex-error"
              >
                <Select
                  id="onboarding-player-sex"
                  value={sex}
                  aria-invalid={Boolean(errors.SEX_REQUIRED || errors.INVALID_SEX)}
                  aria-describedby={
                    errors.SEX_REQUIRED || errors.INVALID_SEX
                      ? "onboarding-player-sex-error"
                      : undefined
                  }
                  className={errors.SEX_REQUIRED || errors.INVALID_SEX ? "input-error" : ""}
                  onChange={(event) => {
                    setSex(event.target.value);
                    setErrors((current) => ({
                      ...current,
                      SEX_REQUIRED: false,
                      INVALID_SEX: false,
                    }));
                    clearActionError();
                  }}
                >
                  <option value="">Selecciona el sexo</option>
                  <option value="female">Femenino</option>
                  <option value="male">Masculino</option>
                </Select>
              </FormField>
            )}

            {store.teams?.length > 1 ? (
              <FormField
                label="Equipo"
                htmlFor="onboarding-team"
                error={errors.TEAM_ID_REQUIRED ? errorMessages.TEAM_ID_REQUIRED : null}
                errorId="onboarding-team-error"
              >
                <Select
                  id="onboarding-team"
                  value={selectedTeam}
                  aria-invalid={Boolean(errors.TEAM_ID_REQUIRED)}
                  aria-describedby={errors.TEAM_ID_REQUIRED ? "onboarding-team-error" : undefined}
                  className={errors.TEAM_ID_REQUIRED ? "input-error" : ""}
                  onChange={(event) => {
                    setSelectedTeam(event.target.value);
                    setErrors((current) => ({ ...current, TEAM_ID_REQUIRED: false }));
                    clearActionError();
                  }}
                >
                  <option value="">Selecciona un equipo</option>
                  {store.teams.map((team) => (
                    <option key={team.id} value={team.id}>{team.name}</option>
                  ))}
                </Select>
              </FormField>
            ) : (
              selectedTeamData && (
                <div className="onboarding-context-card">
                  <span>Equipo</span>
                  <strong>{selectedTeamData.name}</strong>
                </div>
              )
            )}

            {errors.PLAYER_GENDER_MISMATCH && (
              <p className="form-error" role="alert">
                {errorMessages.PLAYER_GENDER_MISMATCH}
              </p>
            )}
            <Button type="submit" disabled={creatingPlayer || finishing}>
              {creatingPlayer || finishing ? "Guardando..." : "Agregar deportista"}
            </Button>
            <button
              type="button"
              className="onboarding-secondary-action"
              onClick={() => requestExit("finish-final")}
              disabled={finishing}
            >
              Lo agregaré después
            </button>
          </form>
        </>
      )}

      {generalError && (
        <div className="onboarding-action-error" role="alert">
          <p>{generalError}</p>
          {retryKind && (
            <button type="button" onClick={handleRetry} disabled={finishing}>
              Reintentar
            </button>
          )}
        </div>
      )}

      {warningAction ? (
        <div className="onboarding-unsaved-warning" role="alert">
          <p>Tienes cambios sin guardar. Si sales ahora, se perderán.</p>
          <div>
            <button type="button" onClick={() => setWarningAction("")}>
              Seguir configurando
            </button>
            <button type="button" onClick={confirmWarning} disabled={finishing}>
              Salir de todos modos
            </button>
          </div>
        </div>
      ) : (
        <div className="onboarding-exit">
          <button
            type="button"
            className="onboarding-skip"
            onClick={() => requestExit("dashboard")}
            disabled={finishing}
          >
            {finishing ? "Guardando..." : "Ir al panel y configurar después"}
          </button>
          <p>
            Podrás crear categorías, equipos y deportistas más adelante desde
            sus módulos.
          </p>
        </div>
      )}
    </AuthLayout>
  );
};

const PlayerField = ({ id, label, value, errorCode, errors, onChange }) => (
  <FormField
    label={label}
    htmlFor={id}
    error={errors[errorCode] ? errorMessages[errorCode] : null}
    errorId={`${id}-error`}
  >
    <Input
      id={id}
      type="text"
      value={value}
      aria-invalid={Boolean(errors[errorCode])}
      aria-describedby={errors[errorCode] ? `${id}-error` : undefined}
      className={errors[errorCode] ? "input-error" : ""}
      onChange={(event) => onChange(event.target.value)}
    />
  </FormField>
);
