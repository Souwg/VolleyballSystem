import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";

export const OnboardingRoute = ({ children }) => {
  const { store } = useContext(Context);

  if (!store.token) {
    return <Navigate to="/login" replace />;
  }

  if (store.user?.first_login) {
    return <Navigate to="/set-password" replace />;
  }

  return children;
};
