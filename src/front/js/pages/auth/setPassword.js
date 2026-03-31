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
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;

    const newErrors = validatePassword(password);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    const result = await actions.setPassword(password);

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
      title="Create password"
      subtitle="You must configure your password"
    >
      <form onSubmit={handleSubmit} className="auth-form">
        <Input
          type="password"
          placeholder="New password"
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

        {errors.PASSWORD_REQUIRED && (
          <p className="form-error">{errorMessages.PASSWORD_REQUIRED}</p>
        )}

        {errors.PASSWORD_TOO_SHORT && (
          <p className="form-error">{errorMessages.PASSWORD_TOO_SHORT}</p>
        )}
        <Button variant="primary" type="submit" disabled={loading}>
          {loading ? "Saving..." : "Save password"}
        </Button>
      </form>
    </AuthLayout>
  );
};
