const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

let actionsRef = null;
let refreshPromise = null;
let firstLoginRedirectPending = false;

const clearLocalSession = () => {
  const hadStoredSession = Boolean(
    localStorage.getItem("token") ||
      localStorage.getItem("user") ||
      localStorage.getItem("refresh")
  );

  localStorage.removeItem("token");
  localStorage.removeItem("user");
  localStorage.removeItem("refresh");

  if (hadStoredSession && actionsRef?.logoutLocal) actionsRef.logoutLocal();
};

const isClubSuspendedResponse = async (response) => {
  if (response?.status !== 403) return false;

  try {
    const data = await response.clone().json();
    return data?.code === "CLUB_SUSPENDED";
  } catch (error) {
    return false;
  }
};

const redirectFirstLoginIfRequired = async (response) => {
  if (response?.status !== 403) return false;

  try {
    const data = await response.clone().json();

    if (data?.code !== "FIRST_LOGIN_REQUIRED") return false;

    const basename = (process.env.BASENAME || "").replace(/\/$/, "");
    const setPasswordPath = `${basename}/set-password`;

    if (
      window.location.pathname !== setPasswordPath &&
      !firstLoginRedirectPending
    ) {
      firstLoginRedirectPending = true;
      window.location.replace(setPasswordPath);
    }

    return true;
  } catch (error) {
    return false;
  }
};

async function refreshToken() {
  const refresh = localStorage.getItem("refresh");

  if (!refresh) {
    return { token: null, response: null, sessionChanged: false };
  }

  try {
    const resp = await fetch(`${BACKEND_URL}/api/refresh`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${refresh}`,
      },
    });

    if (!resp.ok) {
      return {
        token: null,
        response: (await isClubSuspendedResponse(resp)) ? resp : null,
        sessionChanged: false,
      };
    }

    const data = await resp.json();

    // A manual logout or a new login that happens while refresh is pending
    // owns the final session state. Do not restore the previous session.
    if (localStorage.getItem("refresh") !== refresh) {
      return { token: null, response: null, sessionChanged: true };
    }

    localStorage.setItem("token", data.token);
    localStorage.setItem("refresh", data.refresh);

    return { token: data.token, response: null, sessionChanged: false };
  } catch (err) {
    console.error("Error refreshing token:", err);
    return { token: null, response: null, sessionChanged: false };
  }
}

const getSharedRefresh = () => {
  if (!refreshPromise) {
    refreshPromise = refreshToken()
      .then((result) => {
        if (!result.token && !result.sessionChanged) {
          clearLocalSession();
        }

        return result;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

const buildRequestOptions = (options, token) => {
  const headers = new Headers(options.headers || {});
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  if (options.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  headers.set("Authorization", `Bearer ${token}`);

  return {
    ...options,
    headers,
  };
};

const applyResponseGuards = async (response) => {
  if (await isClubSuspendedResponse(response)) {
    clearLocalSession();
    return;
  }

  await redirectFirstLoginIfRequired(response);
};

const cloneResponseIfPossible = (response) =>
  response?.clone ? response.clone() : response;

let showToastGlobal = null;

export const setAuthActions = (actions, toastFn) => {
  if (actions) actionsRef = actions;
  if (toastFn) showToastGlobal = toastFn;
};

export const authFetch = async (endpoint, options = {}) => {
  const requestToken = localStorage.getItem("token");
  const requestUrl = `${BACKEND_URL}${endpoint}`;

  const sendRequest = (token) =>
    fetch(requestUrl, buildRequestOptions(options, token));

  let response = await sendRequest(requestToken);
  await applyResponseGuards(response);

  if (response.status !== 401) return response;

  const currentToken = localStorage.getItem("token");

  // Another request may have completed refresh before this 401 was handled.
  // Retry with that token instead of rotating the session a second time.
  if (currentToken && currentToken !== requestToken) {
    response = await sendRequest(currentToken);
    await applyResponseGuards(response);
    return response;
  }

  const refreshResult = await getSharedRefresh();

  if (!refreshResult.token) {
    if (refreshResult.sessionChanged) return response;

    return cloneResponseIfPossible(refreshResult.response);
  }

  // This direct retry is deliberately not passed through authFetch again:
  // a second 401 is returned to the caller without another refresh attempt.
  response = await sendRequest(refreshResult.token);
  await applyResponseGuards(response);

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
  "EMAIL_ALREADY_EXISTS",
  "INVALID_ROLE",
  "CURRENCY_REQUIRED",
  "INVALID_CURRENCY",

  // LOGIN
  "PASSWORD_REQUIRED",
  "INVALID_CREDENTIALS",
  "ACCOUNT_DISABLED",

  // SET PASSWORD
  "PASSWORD_TOO_SHORT",
  "CONFIRM_PASSWORD_REQUIRED",
  "PASSWORDS_NOT_MATCH",
  "FIRST_LOGIN_ALREADY_COMPLETED",

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
  "TRAINING_CANCELLED",
  "INVALID_ATTENDANCE_STATUS",

  // MATCHES
  "OPPONENT_NAME_REQUIRED",
  "MATCH_DATE_REQUIRED",
  "MATCH_STATUS_REQUIRED",
  "MATCH_PARTICIPATION_REQUIRED",
  "MATCH_ROSTER_REQUIRED",
  "INVALID_MATCH_ROSTER",
  "INVALID_MATCH_STATUS",
  "INVALID_MATCH_TYPE",
  "INVALID_MATCH_RESULT",
  "MATCH_RESULT_INCOMPLETE",
  "MATCH_FINALIZED",
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
  "INITIAL_PAYMENT_MODE_REQUIRED",
  "INITIAL_ENROLLMENT_STATUS_REQUIRED",
  "INVALID_HISTORY_ENROLLMENT_DATE",
  "INVALID_LAST_PAID_MONTH_FORMAT",
  "LAST_PAID_MONTH_BEFORE_ENROLLMENT",
  "LAST_PAID_MONTH_NOT_REACHED",
  "ENROLLMENT_DATE_LOCKED",
  "LEGACY_PAYMENT_HISTORY_REQUIRES_REVIEW",

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
