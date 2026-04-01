const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

let actionsRef = null;
let isRefreshing = false;
async function refreshToken() {
  const refresh = localStorage.getItem("refresh");

  if (!refresh) return null;

  try {
    const resp = await fetch(`${BACKEND_URL}/api/refresh`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${refresh}`,
      },
    });

    if (!resp.ok) return null;

    const data = await resp.json();

    localStorage.setItem("token", data.token);

    localStorage.setItem("refresh", data.refresh);

    return data.token;
  } catch (err) {
    console.error("Error refreshing token:", err);
    return null;
  }
}

let showToastGlobal = null;

export const setAuthActions = (actions, toastFn) => {
  actionsRef = actions;
  showToastGlobal = toastFn;
};

export const authFetch = async (endpoint, options = {}) => {
  const token = localStorage.getItem("token");

  if (!options.headers) options.headers = {};

  if (options.body && !(options.body instanceof FormData)) {
    options.headers["Content-Type"] = "application/json";
  }

  options.headers.Authorization = `Bearer ${token}`;

  let response = await fetch(`${BACKEND_URL}${endpoint}`, options);

  if (response.status === 401 && !isRefreshing) {
    isRefreshing = true;

    const newToken = await refreshToken();

    isRefreshing = false;

    if (!newToken) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      localStorage.removeItem("refresh");

      if (actionsRef?.logoutLocal) actionsRef.logoutLocal();

      return null;
    }

    options.headers.Authorization = `Bearer ${newToken}`;
    response = await fetch(`${BACKEND_URL}${endpoint}`, options);
  }

  return response;
};

import { errorMessages } from "./errorMessages";

const FORM_ERRORS = [
  // CLIENTS
  "FULL_NAME_REQUIRED",
  "EMAIL_REQUIRED",
  "CLUB_NAME_REQUIRED",
  "CLIENT_ALREADY_EXISTS",

  // LOGIN
  "PASSWORD_REQUIRED",
  "INVALID_CREDENTIALS",

  //SET PASSWORD
  "PASSWORD_TOO_SHORT",

  //ONBOARDING
  "LOCATION_REQUIRED",
  "TEAM_NAME_REQUIRED",
  "TEAM_ALREADY_EXISTS",
  "FIRST_NAME_REQUIRED",
  "LAST_NAME_REQUIRED",
  "PLAYER_NUMBER_REQUIRED",
  "INVALID_PLAYER_NUMBER",
  "PLAYER_NUMBER_DUPLICATED",
  "INVALID_SEX",
  "TEAM_ID_REQUIRED",
  "CONFIRM_PASSWORD_REQUIRED",
  "PASSWORDS_NOT_MATCH",
  "INVALID_BIRTH_DATE",
];

export const parseResponse = async (resp) => {
  if (!resp) {
    const message = errorMessages.SESSION_EXPIRED;

    if (showToastGlobal) {
      showToastGlobal(message, "error");
    }

    return {
      ok: false,
      message,
      code: "SESSION_EXPIRED",
      status: 401,
    };
  }

  let data = null;

  try {
    data = await resp.json();
  } catch (e) {}

  if (!resp.ok) {
    const code = data?.code || "UNKNOWN_ERROR";
    const backendMessage = data?.message;

    const finalMessage =
      errorMessages[code] || backendMessage || "Error inesperado";

    if (showToastGlobal && !FORM_ERRORS.includes(code)) {
      showToastGlobal(finalMessage, "error");
    }

    return {
      ok: false,
      message: finalMessage,
      code,
      status: resp.status,
      raw: data,
    };
  }

  if (data?.message && showToastGlobal) {
    showToastGlobal(data.message, "success");
  }

  return {
    ok: true,
    data,
  };
};
