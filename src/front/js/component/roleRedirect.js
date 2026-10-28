import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { Context } from "../store/appContext";

export const getRoleLandingPath = (role) => {
  if (role === "system_admin") return "/admin/clients";

  return "/dashboard";
};

export const getPostLoginPath = (role, onboardingStatus) => {
  if (role === "system_admin") return getRoleLandingPath(role);

  if (onboardingStatus !== "completed") {
    return role === "club_owner" ? "/onboarding" : "/club/setup-pending";
  }

  return getRoleLandingPath(role);
};

export const RoleRedirect = () => {
  const { store } = useContext(Context);

  if (!store.user) {
    return <Navigate to="/login" replace />;
  }

  if (store.user.first_login) {
    return <Navigate to="/set-password" replace />;
  }

  if (store.user.role !== "system_admin" && store.onboardingStatus === null) {
    return null;
  }

  return (
    <Navigate
      to={getPostLoginPath(store.user.role, store.onboardingStatus)}
      replace
    />
  );
};
