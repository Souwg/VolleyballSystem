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

export const setAuthActions = (actions) => {
  actionsRef = actions;
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

export const parseResponse = async (resp) => {
  if (!resp) {
    return {
      ok: false,
      message: "Sesión expirada",
      code: "SESSION_EXPIRED",
      status: 401,
    };
  }

  let data = null;

  try {
    data = await resp.json();
  } catch (e) {}

  if (!resp.ok) {
    return {
      ok: false,
      message: data?.message || "Error inesperado",
      code: data?.code || "UNKNOWN_ERROR",
      status: resp.status,
      raw: data,
    };
  }

  return {
    ok: true,
    data,
  };
};
