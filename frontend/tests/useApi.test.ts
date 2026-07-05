import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { apiFetch } from "../composables/useApi";
import { useAuthStore } from "../app/stores/auth";

const fetchMock = vi.fn();
vi.stubGlobal("$fetch", fetchMock);

const navigateToMock = vi.fn();
vi.stubGlobal("navigateTo", navigateToMock);

const TOKEN_KEY = "adr-flow.access_token";

describe("apiFetch", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    fetchMock.mockReset();
    navigateToMock.mockReset();
    sessionStorage.clear();
    window.history.pushState({}, "", "/workspace");
  });

  it("attaches Authorization header when an access token is stored", async () => {
    sessionStorage.setItem(TOKEN_KEY, "stored-token");
    fetchMock.mockResolvedValue({ ok: true });

    await apiFetch("/api/adrs");

    expect(fetchMock).toHaveBeenCalledWith("/api/adrs", {
      headers: { Authorization: "Bearer stored-token" },
    });
  });

  it("clears auth and redirects to login on 401 outside auth pages", async () => {
    sessionStorage.setItem(TOKEN_KEY, "expired-token");
    const store = useAuthStore();
    store.user = {
      id: "user-1",
      email: "test@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    };

    const error = Object.assign(new Error("Unauthorized"), { status: 401 });
    fetchMock.mockRejectedValue(error);

    await expect(apiFetch("/api/adrs")).rejects.toThrow("Unauthorized");

    expect(store.user).toBeNull();
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(navigateToMock).toHaveBeenCalledWith("/login");
  });

  it("does not redirect to login on 401 when already on /login", async () => {
    window.history.pushState({}, "", "/login");
    fetchMock.mockRejectedValue(
      Object.assign(new Error("Unauthorized"), { status: 401 }),
    );

    await expect(apiFetch("/api/auth/me")).rejects.toThrow("Unauthorized");

    expect(navigateToMock).not.toHaveBeenCalled();
  });
});
