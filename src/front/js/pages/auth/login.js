import React, { useState, useContext } from "react";
import { Context } from "../../store/appContext";
import { useNavigate } from "react-router-dom";
import { AuthLayout } from "../../component/authLayout";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { validateLogin } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

export const Login = () => {
  const { actions } = useContext(Context);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (loading) return;

    const newErrors = validateLogin({ email, password });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});

    setLoading(true);

    const result = await actions.loginUser(email.trim(), password);

    if (!result?.ok) {
      setErrors({ [result.code]: true });
      setLoading(false);
      return;
    }
    if (result.data.first_login === true) {
      navigate("/set-password", { replace: true });
      return;
    }

    const role = result.data.user.role;

    if (role === "system_admin") {
      navigate("/admin/clients", { replace: true });
    } else {
      await actions.getOnboardingStatus();
      navigate("/dashboard", { replace: true });
    }
  };
  return (
    <AuthLayout
      title="Bienvenida de nuevo"
      subtitle="Ingresa a tu panel del club"
    >
      <form onSubmit={handleLogin} className="auth-form" noValidate>
        <div className="auth-field">
          <label className="auth-label">Email</label>

          <Input
            type="email"
            placeholder="tu@email.com"
            value={email}
            className={
              errors.EMAIL_REQUIRED ||
              errors.INVALID_EMAIL ||
              errors.INVALID_CREDENTIALS ||
              errors.ACCOUNT_DISABLED
                ? "input-error"
                : ""
            }
            onChange={(e) => {
              setEmail(e.target.value);
              setErrors((prev) => ({
                ...prev,
                EMAIL_REQUIRED: false,
                INVALID_EMAIL: false,
                INVALID_CREDENTIALS: false,
                ACCOUNT_DISABLED: false,
              }));
            }}
          />

          {errors.EMAIL_REQUIRED && (
            <p className="form-error">{errorMessages.EMAIL_REQUIRED}</p>
          )}

          {errors.INVALID_EMAIL && (
            <p className="form-error">{errorMessages.INVALID_EMAIL}</p>
          )}
        </div>

        <div className="auth-field">
          <label className="auth-label">Contraseña</label>

          <div className="password-field">
            <Input
              type={showPassword ? "text" : "password"}
              placeholder="Tu contraseña"
              value={password}
              className={
                errors.PASSWORD_REQUIRED ||
                errors.INVALID_CREDENTIALS ||
                errors.ACCOUNT_DISABLED
                  ? "input-error"
                  : ""
              }
              onChange={(e) => {
                setPassword(e.target.value);
                setErrors((prev) => ({
                  ...prev,
                  PASSWORD_REQUIRED: false,
                  INVALID_CREDENTIALS: false,
                  ACCOUNT_DISABLED: false,
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

          {errors.INVALID_CREDENTIALS && (
            <p className="form-error">{errorMessages.INVALID_CREDENTIALS}</p>
          )}

          {errors.ACCOUNT_DISABLED && (
            <p className="form-error">{errorMessages.ACCOUNT_DISABLED}</p>
          )}
        </div>

        <Button type="submit" disabled={loading}>
          {loading ? "Ingresando..." : "Ingresar"}
        </Button>
      </form>
    </AuthLayout>
  );
};
