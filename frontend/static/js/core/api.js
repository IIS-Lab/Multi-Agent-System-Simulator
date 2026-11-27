// JSON fetch wrapper for the application backend. Secrets never reach the browser.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, redirectOn401 = true } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Could not reach the server. Check your connection.", 0);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (response.status === 401 && redirectOn401) {
      window.location.href = "/login";
    }
    const detail = data && typeof data.detail === "string" ? data.detail : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(detail, response.status);
  }
  return data;
}
