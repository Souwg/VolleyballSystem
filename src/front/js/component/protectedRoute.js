import React, { useContext } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Context } from "../store/appContext";
import { getPostLoginPath, getRoleLandingPath } from "./roleRedirect";

export const ProtectedRoute = ({ allowFirstLogin = false }) => {
  const { store } = useContext(Context);
  const location = useLocation();

  if (!store.token) {
    return <Navigate to="/login" replace />;
  }

  if (store.user?.first_login && !allowFirstLogin) {
    return <Navigate to="/set-password" replace />;
  }

  if (
    store.user?.role === "system_admin" &&
    location.pathname === "/club/setup-pending"
  ) {
    return <Navigate to={getRoleLandingPath(store.user.role)} replace />;
  }

  if (store.user?.role === "system_admin" || store.user?.first_login) {
    return <Outlet />;
  }

  if (store.onboardingStatus === null) {
    if (
      location.pathname === "/club/setup-pending" &&
      ["coach", "staff"].includes(store.user?.role)
    ) {
      return <Outlet />;
    }

    return null;
  }

  const destination = getPostLoginPath(
    store.user?.role,
    store.onboardingStatus
  );

  if (store.onboardingStatus !== "completed") {
    if (location.pathname !== destination) {
      return <Navigate to={destination} replace />;
    }

    return <Outlet />;
  }

  if (location.pathname === "/club/setup-pending") {
    return <Navigate to={getRoleLandingPath(store.user?.role)} replace />;
  }

  return <Outlet />;
};
