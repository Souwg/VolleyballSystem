import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";
import { getPostLoginPath, getRoleLandingPath } from "./roleRedirect";

export const OnboardingRoute = ({ children }) => {
  const { store } = useContext(Context);

  if (!store.token) {
    return <Navigate to="/login" replace />;
  }

  if (store.user?.first_login) {
    return <Navigate to="/set-password" replace />;
  }

  if (store.user?.role === "system_admin") {
    return <Navigate to={getRoleLandingPath(store.user.role)} replace />;
  }

  if (store.user?.role !== "club_owner") {
    return (
      <Navigate
        to={getPostLoginPath(store.user?.role, store.onboardingStatus)}
        replace
      />
    );
  }

  if (store.onboardingStatus === "completed") {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};
