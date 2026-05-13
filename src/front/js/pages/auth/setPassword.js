import React, { useState, useContext } from "react";
import { Context } from "../../store/appContext";
import { useNavigate } from "react-router-dom";
import { AuthLayout } from "../../component/authLayout";

import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { validatePassword } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

export const SetPassword = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;

    const newErrors = validatePassword(password, confirmPassword);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const cleanPassword = password.trim();

    const result = await actions.setPassword(cleanPassword);

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }

    await actions.getOnboardingStatus();
    navigate("/dashboard", { replace: true });
  };

  return (
    <AuthLayout
      title="Crear contraseña"
      subtitle="Configura tu nueva contraseña para activar tu acceso"
    >
      <form onSubmit={handleSubmit} className="auth-form">
        <div className="auth-field">
          <label className="auth-label">Nueva contraseña</label>

          <div className="password-field">
            <Input
              type={showPassword ? "text" : "password"}
              placeholder="Mínimo 8 caracteres"
              value={password}
              className={
                errors.PASSWORD_REQUIRED || errors.PASSWORD_TOO_SHORT
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setPassword(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  PASSWORD_REQUIRED: false,
                  PASSWORD_TOO_SHORT: false,
                }));
              }}
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((prev) => !prev)}
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
          <label className="auth-label">Confirmar contraseña</label>

          <div className="password-field">
            <Input
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Repite tu contraseña"
              value={confirmPassword}
              className={
                errors.CONFIRM_PASSWORD_REQUIRED || errors.PASSWORDS_NOT_MATCH
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  CONFIRM_PASSWORD_REQUIRED: false,
                  PASSWORDS_NOT_MATCH: false,
                }));
              }}
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
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

          {confirmPassword && password === confirmPassword && (
            <p className="form-success">Las contraseñas coinciden</p>
          )}

          {confirmPassword && password && password !== confirmPassword && (
            <p className="form-error">{errorMessages.PASSWORDS_NOT_MATCH}</p>
          )}
        </div>

        <Button variant="primary" type="submit" disabled={loading}>
          {loading ? "Guardando..." : "Guardar contraseña"}
        </Button>
      </form>
    </AuthLayout>
  );
};
