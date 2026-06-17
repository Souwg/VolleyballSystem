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
  "INVALID_EMAIL",
  "CLUB_NAME_REQUIRED",
  "STATE_REQUIRED",
  "CLIENT_ALREADY_EXISTS",

  // LOGIN
  "PASSWORD_REQUIRED",
  "INVALID_CREDENTIALS",
  "ACCOUNT_DISABLED",

  // SET PASSWORD
  "PASSWORD_TOO_SHORT",
  "CONFIRM_PASSWORD_REQUIRED",
  "PASSWORDS_NOT_MATCH",

  // ONBOARDING / CLUB / TEAMS / PLAYERS
  "LOCATION_REQUIRED",
  "INVALID_DEFAULT_ENROLLMENT_FEE",
  "INVALID_DEFAULT_MONTHLY_FEE",
  "CATEGORY_NAME_REQUIRED",
  "CATEGORY_ALREADY_EXISTS",
  "CATEGORY_ID_REQUIRED",
  "TEAM_NAME_REQUIRED",
  "TEAM_ALREADY_EXISTS",
  "INVALID_TEAM_GENDER",
  "FIRST_NAME_REQUIRED",
  "LAST_NAME_REQUIRED",
  "PLAYER_NUMBER_REQUIRED",
  "INVALID_PLAYER_NUMBER",
  "PLAYER_NUMBER_DUPLICATED",
  "INVALID_SEX",
  "PLAYER_GENDER_MISMATCH",
  "PLAYER_NOT_FOUND",
  "INVALID_PLAYER_STATUS",
  "INVALID_PLAYER_ACTIVE_STATUS",
  "PLAYER_HAS_HISTORY",
  "SEX_REQUIRED",
  "TEAM_ID_REQUIRED",
  "INVALID_BIRTH_DATE",
  "PLAYER_REQUIRED",
  "INVALID_DATE_FORMAT",

  // TRAININGS
  "TRAINING_DATE_REQUIRED",
  "TRAINING_LOCATION_REQUIRED",
  "ATTENDANCE_REQUIRED",
  "TEAM_NOT_FOUND",
  "TRAINING_NOT_FOUND",
  "INVALID_ATTENDANCE_STATUS",

  // MATCHES
  "OPPONENT_NAME_REQUIRED",
  "MATCH_DATE_REQUIRED",
  "MATCH_STATUS_REQUIRED",
  "MATCH_PARTICIPATION_REQUIRED",
  "MATCH_ROSTER_REQUIRED",
  "INVALID_MATCH_STATUS",
  "INVALID_MATCH_TYPE",
  "INVALID_MATCH_RESULT",
  "INVALID_ATTACK_STATS",
  "INVALID_RECEPTION_STATS",
  "INVALID_SERVE_STATS",
  "INVALID_BLOCK_STATS",
  "INVALID_POSITION",
  "POSITION_REQUIRED",

  // IMAGES
  "IMAGE_TOO_LARGE",
  "IMAGE_REQUIRED",
  "INVALID_IMAGE_FORMAT",

  // PAYMENTS
  "ENROLLMENT_DATE_REQUIRED",
  "CLUB_PAYMENT_DEFAULTS_REQUIRED",
  "ENROLLMENT_FEE_REQUIRED",
  "MONTHLY_FEE_REQUIRED",
  "INVALID_ENROLLMENT_FEE",
  "INVALID_MONTHLY_FEE",
  "PAYMENT_DATE_REQUIRED",
  "PAYMENT_METHOD_REQUIRED",
  "INVALID_PAYMENT_METHOD",
  "INVALID_PAYMENT_AMOUNT",
  "INVALID_PAYMENT_STATUS",
  "INVALID_PAYMENT_TYPE",
  "PAYMENT_NOT_FOUND",
  "INVALID_DUE_DATE_FORMAT",
  "INVALID_ENROLLMENT_DATE_FORMAT",

  "MATCH_PLAYER_ID_REQUIRED",
  "MATCH_PLAYER_NOT_FOUND",
  "MATCH_PLAYER_INVALID",
  "PLAYER_NOT_CALLED",
  "PLAYER_NOT_ELIGIBLE_FOR_PARTICIPATION",
  "PLAYER_NOT_ELIGIBLE_FOR_STATS",
  "PLAYER_NOT_ELIGIBLE_FOR_LINEUP",
  "STARTING_LINEUP_REQUIRED",
  "STARTING_LINEUP_MUST_HAVE_6",
  "INVALID_STARTING_LINEUP",
  "PAYMENT_NOT_PAID",
  "RECEIPT_NOT_FOUND",
  "INVALID_RECEIPT_CHANNEL",
  "INVALID_PAYMENT_DATE",
  "CLUB_NOT_FOUND",
  "PLAYER_INACTIVE",
  "RECEIPT_NOT_FOUND",
  "PAYMENT_NOT_PAID",
  "INVALID_RECEIPT_CHANNEL",
  "INVALID_PAYMENT_DATE",
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
