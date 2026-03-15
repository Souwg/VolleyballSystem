import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";

export const ProtectedRoute = ({ children, allowFirstLogin = false }) => {
  const { store } = useContext(Context);

  if (!store.token) {
    return <Navigate to="/login" replace />;
  }

  // esperar a que cargue el onboarding
  if (
    store.user?.role !== "system_admin" &&
    !store.user?.first_login &&
    store.onboardingStatus === null
  ) {
    return null;
  }
  // obligar a cambiar contraseña primero
  if (store.user?.first_login && !allowFirstLogin) {
    return <Navigate to="/set-password" replace />;
  }

  // bloquear acceso al sistema si onboarding no está completo
  if (
    store.user?.role !== "system_admin" &&
    !store.user?.first_login &&
    store.onboardingStatus !== "completed"
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return children;
};
