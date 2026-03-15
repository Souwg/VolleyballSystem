import React, { useState, useContext } from "react";
import { Context } from "../../store/appContext";
import { useNavigate } from "react-router-dom";
import { AuthLayout } from "../../component/authLayout";

export const SetPassword = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    const result = await actions.setPassword(password);

    if (!result.success) {
      setError(result.message);
      return;
    }

    await actions.getOnboardingStatus();

    navigate("/dashboard");
  };

  return (
    <AuthLayout
      title="Create password"
      subtitle="You must configure your password"
    >
      {error && <p className="auth-error">{error}</p>}

      <form onSubmit={handleSubmit} className="auth-form">
        <input
          type="password"
          placeholder="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button type="submit">Save password</button>
      </form>
    </AuthLayout>
  );
};
