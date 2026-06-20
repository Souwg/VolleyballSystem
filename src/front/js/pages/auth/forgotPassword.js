import React, { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Mail, CheckCircle2 } from "lucide-react";

import { Context } from "../../store/appContext";
import { AuthLayout } from "../../component/authLayout";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";

import { validateForgotPassword } from "../../utils/validators";
import { errorMessages } from "../../utils/errorMessages";

export const ForgotPassword = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [requestSent, setRequestSent] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (loading) return;

    const validationErrors = validateForgotPassword({ email });

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.requestPasswordReset(email.trim());

    setLoading(false);

    if (!result?.ok) {
      setErrors({
        [result?.code || "NETWORK_ERROR"]: true,
      });
      return;
    }

    setRequestSent(true);
  };

  if (requestSent) {
    return (
      <AuthLayout
        title="Revisa tu correo"
        subtitle="Te enviaremos instrucciones si existe una cuenta asociada."
      >
        <div className="auth-result">
          <div className="auth-result-icon">
            <CheckCircle2 size={28} aria-hidden="true" />
          </div>

          <p>
            Si existe una cuenta registrada con <strong>{email.trim()}</strong>,
            recibirás un enlace para crear una nueva contraseña.
          </p>

          <p className="auth-helper-text">
            El enlace tendrá una duración limitada. También puedes revisar la
            carpeta de correo no deseado.
          </p>

          <Button type="button" onClick={() => navigate("/login")}>
            Volver al inicio de sesión
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Recuperar contraseña"
      subtitle="Ingresa el correo asociado a tu cuenta."
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <div className="auth-field">
          <label className="auth-label" htmlFor="recovery-email">
            Email
          </label>

          <div className="auth-input-with-icon">
            <Mail className="auth-input-icon" size={18} aria-hidden="true" />

            <Input
              id="recovery-email"
              type="email"
              autoComplete="email"
              placeholder="tu@email.com"
              value={email}
              className={
                errors.EMAIL_REQUIRED || errors.INVALID_EMAIL
                  ? "input-error"
                  : ""
              }
              onChange={(event) => {
                setEmail(event.target.value);

                setErrors((previous) => ({
                  ...previous,
                  EMAIL_REQUIRED: false,
                  INVALID_EMAIL: false,
                  NETWORK_ERROR: false,
                }));
              }}
            />
          </div>

          {errors.EMAIL_REQUIRED && (
            <p className="form-error">{errorMessages.EMAIL_REQUIRED}</p>
          )}

          {errors.INVALID_EMAIL && (
            <p className="form-error">{errorMessages.INVALID_EMAIL}</p>
          )}
        </div>

        {errors.NETWORK_ERROR && (
          <p className="form-error">{errorMessages.NETWORK_ERROR}</p>
        )}

        <Button type="submit" disabled={loading}>
          {loading ? "Enviando..." : "Enviar instrucciones"}
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
