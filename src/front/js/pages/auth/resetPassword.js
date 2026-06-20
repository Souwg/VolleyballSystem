import React, { useContext, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, KeyRound, ShieldAlert } from "lucide-react";

import { Context } from "../../store/appContext";
import { AuthLayout } from "../../component/authLayout";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";

import { validatePassword } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

export const ResetPassword = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useMemo(
    () => searchParams.get("token")?.trim() || "",
    [searchParams],
  );

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [passwordUpdated, setPasswordUpdated] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (loading) return;

    if (!token) {
      setErrors({
        RESET_TOKEN_REQUIRED: true,
      });
      return;
    }

    const validationErrors = validatePassword(password, confirmPassword);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.resetPassword(token, password);

    setLoading(false);

    if (!result?.ok) {
      setErrors({
        [result?.code || "NETWORK_ERROR"]: true,
      });
      return;
    }

    setPasswordUpdated(true);
  };

  if (!token) {
    return (
      <AuthLayout
        title="Enlace no válido"
        subtitle="No encontramos un token de recuperación."
      >
        <div className="auth-result">
          <div className="auth-result-icon auth-result-icon-error">
            <ShieldAlert size={28} aria-hidden="true" />
          </div>

          <p>
            Este enlace está incompleto o no es válido. Solicita un nuevo enlace
            de recuperación.
          </p>

          <Button
            type="button"
            onClick={() => navigate("/forgot-password", { replace: true })}
          >
            Solicitar un nuevo enlace
          </Button>

          <button
            type="button"
            className="auth-back-link"
            onClick={() => navigate("/login")}
          >
            <ArrowLeft size={16} aria-hidden="true" />
            Volver al inicio de sesión
          </button>
        </div>
      </AuthLayout>
    );
  }

  if (passwordUpdated) {
    return (
      <AuthLayout
        title="Contraseña actualizada"
        subtitle="Tu acceso fue restablecido correctamente."
      >
        <div className="auth-result">
          <div className="auth-result-icon">
            <CheckCircle2 size={28} aria-hidden="true" />
          </div>

          <p>Ya puedes ingresar a SportFlow utilizando tu nueva contraseña.</p>

          <Button
            type="button"
            onClick={() => navigate("/login", { replace: true })}
          >
            Iniciar sesión
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Crear nueva contraseña"
      subtitle="Elige una contraseña segura para recuperar tu acceso."
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <div className="auth-security-note">
          <KeyRound size={18} aria-hidden="true" />

          <span>La contraseña debe tener al menos 8 caracteres.</span>
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="new-password">
            Nueva contraseña
          </label>

          <div className="password-field">
            <Input
              id="new-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Mínimo 8 caracteres"
              value={password}
              className={
                errors.PASSWORD_REQUIRED || errors.PASSWORD_TOO_SHORT
                  ? "input-error"
                  : ""
              }
              onChange={(event) => {
                setPassword(event.target.value);

                setErrors((previous) => ({
                  ...previous,
                  PASSWORD_REQUIRED: false,
                  PASSWORD_TOO_SHORT: false,
                  PASSWORDS_NOT_MATCH: false,
                  RESET_TOKEN_INVALID: false,
                  RESET_TOKEN_EXPIRED: false,
                  NETWORK_ERROR: false,
                }));
              }}
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((previous) => !previous)}
            >
              {showPassword ? "Ocultar" : "Ver"}
            </button>
          </div>

          {errors.PASSWORD_REQUIRED && (
            <p className="form-error">{errorMessages.PASSWORD_REQUIRED}</p>
          )}

          {errors.PASSWORD_TOO_SHORT && (
            <p className="form-error">{errorMessages.PASSWORD_TOO_SHORT}</p>
          )}
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="confirm-new-password">
            Confirmar contraseña
          </label>

          <div className="password-field">
            <Input
              id="confirm-new-password"
              type={showConfirmPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="Repite tu contraseña"
              value={confirmPassword}
              className={
                errors.CONFIRM_PASSWORD_REQUIRED || errors.PASSWORDS_NOT_MATCH
                  ? "input-error"
                  : ""
              }
              onChange={(event) => {
                setConfirmPassword(event.target.value);

                setErrors((previous) => ({
                  ...previous,
                  CONFIRM_PASSWORD_REQUIRED: false,
                  PASSWORDS_NOT_MATCH: false,
                  RESET_TOKEN_INVALID: false,
                  RESET_TOKEN_EXPIRED: false,
                  NETWORK_ERROR: false,
                }));
              }}
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowConfirmPassword((previous) => !previous)}
            >
              {showConfirmPassword ? "Ocultar" : "Ver"}
            </button>
          </div>

          {errors.CONFIRM_PASSWORD_REQUIRED && (
            <p className="form-error">
              {errorMessages.CONFIRM_PASSWORD_REQUIRED}
            </p>
          )}

          {errors.PASSWORDS_NOT_MATCH && (
            <p className="form-error">{errorMessages.PASSWORDS_NOT_MATCH}</p>
          )}
        </div>

        {(errors.RESET_TOKEN_REQUIRED ||
          errors.RESET_TOKEN_INVALID ||
          errors.RESET_TOKEN_EXPIRED ||
          errors.USER_NOT_FOUND ||
          errors.NETWORK_ERROR) && (
          <p className="form-error">
            {errors.RESET_TOKEN_REQUIRED
              ? errorMessages.RESET_TOKEN_REQUIRED
              : errors.RESET_TOKEN_INVALID
              ? errorMessages.RESET_TOKEN_INVALID
              : errors.RESET_TOKEN_EXPIRED
              ? errorMessages.RESET_TOKEN_EXPIRED
              : errors.USER_NOT_FOUND
              ? errorMessages.USER_NOT_FOUND
              : errorMessages.NETWORK_ERROR}
          </p>
        )}

        <Button type="submit" disabled={loading}>
          {loading ? "Actualizando..." : "Guardar nueva contraseña"}
        </Button>

        <button
          type="button"
          className="auth-back-link"
          onClick={() => navigate("/login")}
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Volver al inicio de sesión
        </button>
      </form>
    </AuthLayout>
  );
};
