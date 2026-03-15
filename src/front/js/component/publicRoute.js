import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";

export const PublicRoute = ({ children }) => {
  const { store } = useContext(Context);

  // si ya está logueado no puede ir al login
  if (store.token) {
    return <Navigate to="/" replace />;
  }

  return children;
};
