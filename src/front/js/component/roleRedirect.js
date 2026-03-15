import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";

export const RoleRedirect = () => {
  const { store } = useContext(Context);

  if (!store.user) {
    return <Navigate to="/login" replace />;
  }

  if (store.user.role === "system_admin") {
    return <Navigate to="/admin/clients" replace />;
  }

  return <Navigate to="/dashboard" replace />;
};
