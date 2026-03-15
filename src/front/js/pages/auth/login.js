import React, { useState, useContext } from "react";
import { Context } from "../../store/appContext";
import { useNavigate } from "react-router-dom";
import { AuthLayout } from "../../component/authLayout";

export const Login = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();

    const result = await actions.loginUser(email, password);

    if (!result.success) {
      alert(result.message);
      return;
    }

    if (result.first_login === true) {
      navigate("/set-password", { replace: true });
      return;
    }

    const role = result.user.role;

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
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button type="submit">Login</button>
      </form>
    </AuthLayout>
  );
};
