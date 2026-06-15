import path from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { getAuthErrorMessage, useAuthStore } from "../app/stores/auth";

vi.mock("../composables/useApi", () => ({
  apiPath: (segment: string) => `/api${segment}`,
}));

const fetchMock = vi.fn();
vi.stubGlobal("$fetch", fetchMock);

describe("useAuthStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    fetchMock.mockReset();
  });

  it("fetchUser hydrates the current user from the session cookie", async () => {
    fetchMock.mockResolvedValue({
      id: "user-1",
      email: "test@example.com",
      created_at: "2026-01-01T00:00:00Z",
    });

    const store = useAuthStore();
    const ok = await store.fetchUser();

    expect(ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/me");
    expect(store.user).toEqual({
      id: "user-1",
      email: "test@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    });
    expect(store.isAuthenticated).toBe(true);
  });

  it("fetchUser clears user state when the session is missing", async () => {
    fetchMock.mockRejectedValue(new Error("Unauthorized"));

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

  it("register stores the returned user", async () => {
    fetchMock.mockResolvedValue({
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
    expect(store.user?.email).toBe("new@example.com");
    expect(store.isAuthenticated).toBe(true);
  });

  it("login stores the returned user", async () => {
    fetchMock.mockResolvedValue({
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
    expect(store.user?.email).toBe("login@example.com");
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
