import React, { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthLayout } from "../../component/authLayout";
import { getRoleLandingPath } from "../../component/roleRedirect";
import { Button } from "../../component/ui/button";
import { Context } from "../../store/appContext";
import { errorMessages } from "../../utils/errorMessages";
import "../../../styles/clubSetupPending.css";


export const ClubSetupPending = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const clubName = store.user?.club?.name || store.club?.name;

  const handleRetry = async () => {
    if (checking) return;

    setChecking(true);
    setError("");

    const result = await actions.getOnboardingStatus();

    if (!result?.ok) {
      setError(
        result?.message ||
        errorMessages[result?.code] ||
        errorMessages.NETWORK_ERROR
      );
      setChecking(false);
      return;
    }

    if (result.data.status === "completed") {
      navigate(getRoleLandingPath(store.user?.role), { replace: true });
      return;
    }

    setChecking(false);
  };

  const handleLogout = async () => {
    await actions.logoutUser();
    navigate("/login", { replace: true });
  };

  return (
    <AuthLayout
      title="Club en configuración"
      subtitle="El administrador del club debe completar la configuración inicial antes de que puedas comenzar a usar SportFlow."
    >
      <div className="auth-form setup-pending-content">
        {clubName && (
          <p className="setup-pending-club">
            Club: <strong>{clubName}</strong>
          </p>
        )}

        {error && <p className="form-error">{error}</p>}

        <Button type="button" onClick={handleRetry} disabled={checking}>
          {checking ? "Revisando..." : "Revisar nuevamente"}
        </Button>

        <Button type="button" variant="secondary" onClick={handleLogout}>
          Cerrar sesión
        </Button>
      </div>
    </AuthLayout>
  );
};
