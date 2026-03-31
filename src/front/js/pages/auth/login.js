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
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    const newErrors = validateLogin({ email, password });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});

    const result = await actions.loginUser(email, password);

    if (!result?.ok) {
      setErrors({ [result.code]: true });
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
    <AuthLayout title="Welcome back" subtitle="Login to your club dashboard">
      <form onSubmit={handleLogin} className="auth-form">
        <div>
          <Input
            type="email"
            placeholder="Email"
            value={email}
            className={
              errors.EMAIL_REQUIRED ||
              errors.INVALID_EMAIL ||
              errors.INVALID_CREDENTIALS
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

        <div>
          <Input
            type="password"
            placeholder="Password"
            value={password}
            className={
              errors.PASSWORD_REQUIRED || errors.INVALID_CREDENTIALS
                ? "input-error"
                : ""
            }
            onChange={(e) => {
              setPassword(e.target.value);
              setErrors((prev) => ({
                ...prev,
                PASSWORD_REQUIRED: false,
                INVALID_CREDENTIALS: false,
              }));
            }}
          />

          {errors.PASSWORD_REQUIRED && (
            <p className="form-error">{errorMessages.PASSWORD_REQUIRED}</p>
          )}

          {errors.INVALID_CREDENTIALS && (
            <p className="form-error">{errorMessages.INVALID_CREDENTIALS}</p>
          )}
        </div>

        <Button type="submit">Login</Button>
      </form>
    </AuthLayout>
  );
};
