import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { getAuthErrorMessage, useAuthStore } from "../app/stores/auth";

const apiFetchMock = vi.fn();

vi.mock("../composables/useApi", () => ({
  apiPath: (segment: string) => `/api${segment}`,
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

const fetchMock = vi.fn();
vi.stubGlobal("$fetch", fetchMock);

const TOKEN_KEY = "adr-flow.access_token";

describe("useAuthStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    fetchMock.mockReset();
    apiFetchMock.mockReset();
    sessionStorage.clear();
  });

  it("fetchUser hydrates the current user with Bearer token", async () => {
    sessionStorage.setItem(TOKEN_KEY, "me-token");
    apiFetchMock.mockResolvedValue({
      id: "user-1",
      email: "test@example.com",
      created_at: "2026-01-01T00:00:00Z",
    });

    const store = useAuthStore();
    const ok = await store.fetchUser();

    expect(ok).toBe(true);
    expect(apiFetchMock).toHaveBeenCalledWith("/api/auth/me");
    expect(store.user).toEqual({
      id: "user-1",
      email: "test@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    });
    expect(store.isAuthenticated).toBe(true);
  });

  it("fetchUser clears user state when the token is invalid", async () => {
    apiFetchMock.mockRejectedValue(new Error("Unauthorized"));

    const store = useAuthStore();
    store.user = {
      id: "stale",
      email: "stale@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    };

    const ok = await store.fetchUser();

    expect(ok).toBe(false);
    expect(store.user).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });

  it("register stores access token and hydrates user via /me", async () => {
    fetchMock.mockResolvedValue({ access_token: "register-token" });
    apiFetchMock.mockResolvedValue({
      id: "user-2",
      email: "new@example.com",
      created_at: "2026-06-15T12:00:00Z",
    });

    const store = useAuthStore();
    await store.register("new@example.com", "password123");

    expect(fetchMock).toHaveBeenCalledWith("/api/auth/register", {
      method: "POST",
      body: { email: "new@example.com", password: "password123" },
    });
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe("register-token");
    expect(apiFetchMock).toHaveBeenCalledWith("/api/auth/me");
    expect(store.user?.email).toBe("new@example.com");
    expect(store.isAuthenticated).toBe(true);
  });

  it("login stores access token and hydrates user via /me", async () => {
    fetchMock.mockResolvedValue({ access_token: "login-token" });
    apiFetchMock.mockResolvedValue({
      id: "user-3",
      email: "login@example.com",
      created_at: "2026-06-15T12:00:00Z",
    });

    const store = useAuthStore();
    await store.login("login@example.com", "secret123");

    expect(fetchMock).toHaveBeenCalledWith("/api/auth/login", {
      method: "POST",
      body: { email: "login@example.com", password: "secret123" },
    });
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe("login-token");
    expect(apiFetchMock).toHaveBeenCalledWith("/api/auth/me");
    expect(store.user?.email).toBe("login@example.com");
  });

  it("clearAuth removes user state and stored token", () => {
    sessionStorage.setItem(TOKEN_KEY, "logout-token");

    const store = useAuthStore();
    store.user = {
      id: "user-1",
      email: "test@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    };

    store.clearAuth();

    expect(store.user).toBeNull();
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});

describe("getAuthErrorMessage", () => {
  it("returns API detail when present", () => {
    const error = {
      data: { detail: "Invalid email or password" },
    };

    expect(getAuthErrorMessage(error, "fallback")).toBe(
      "Invalid email or password",
    );
  });

  it("falls back when detail is missing", () => {
    expect(getAuthErrorMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
