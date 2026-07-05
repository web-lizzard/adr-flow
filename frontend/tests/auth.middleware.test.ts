import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useAuthStore as useAuthStoreImpl } from "../app/stores/auth";

const { navigateToMock, apiFetchMock } = vi.hoisted(() => ({
  navigateToMock: vi.fn(),
  apiFetchMock: vi.fn(),
}));

vi.hoisted(() => {
  vi.stubGlobal("navigateTo", navigateToMock);
  vi.stubGlobal(
    "defineNuxtRouteMiddleware",
    (handler: unknown) => handler as () => Promise<unknown>,
  );
});

vi.mock("../composables/useApi", () => ({
  apiPath: (segment: string) => `/api${segment}`,
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

type RouteMiddleware = (
  to: unknown,
  from: unknown,
) => Promise<unknown> | unknown;

let authMiddleware: RouteMiddleware;
let guestMiddleware: RouteMiddleware;

beforeAll(async () => {
  vi.stubGlobal("useAuthStore", useAuthStoreImpl);
  authMiddleware = (await import("../app/middleware/auth")).default;
  guestMiddleware = (await import("../app/middleware/guest")).default;
});

describe("auth middleware", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    navigateToMock.mockReset();
    apiFetchMock.mockReset();
  });

  it("redirects to login on client when fetchUser fails", async () => {
    apiFetchMock.mockRejectedValue(new Error("Unauthorized"));

    await authMiddleware({}, {});

    expect(navigateToMock).toHaveBeenCalledWith("/login");
  });

  it("allows navigation when the user is already hydrated", async () => {
    const store = useAuthStoreImpl();
    store.user = {
      id: "user-1",
      email: "test@example.com",
      createdAt: "2026-01-01T00:00:00Z",
    };

    const result = await authMiddleware({}, {});

    expect(apiFetchMock).not.toHaveBeenCalled();
    expect(navigateToMock).not.toHaveBeenCalled();
    expect(result).toBeUndefined();
  });
});

describe("guest middleware", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    navigateToMock.mockReset();
    apiFetchMock.mockReset();
  });

  it("redirects authenticated users to workspace", async () => {
    apiFetchMock.mockResolvedValue({
      id: "user-1",
      email: "test@example.com",
      created_at: "2026-01-01T00:00:00Z",
    });

    await guestMiddleware({}, {});

    expect(navigateToMock).toHaveBeenCalledWith("/workspace");
  });
});
