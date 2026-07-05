import { apiFetch, apiPath } from "../../composables/useApi";
import {
  clearAccessToken,
  setAccessToken,
} from "../../composables/useAuthToken";

export type AuthUser = {
  id: string;
  email: string;
  createdAt: string;
};

type UserResponse = {
  id: string;
  email: string;
  created_at: string;
};

type AuthResponse = {
  access_token: string;
};

function toAuthUser(response: UserResponse): AuthUser {
  return {
    id: response.id,
    email: response.email,
    createdAt: response.created_at,
  };
}

export const useAuthStore = defineStore("auth", () => {
  const user = ref<AuthUser | null>(null);
  const loading = ref(false);

  const isAuthenticated = computed(() => user.value !== null);

  function clearAuth(): void {
    user.value = null;
    clearAccessToken();
  }

  async function fetchUser(): Promise<boolean> {
    loading.value = true;
    try {
      const response = await apiFetch<UserResponse>(apiPath("/auth/me"));
      user.value = toAuthUser(response);
      return true;
    } catch {
      user.value = null;
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function register(email: string, password: string): Promise<void> {
    loading.value = true;
    try {
      const response = await $fetch<AuthResponse>(apiPath("/auth/register"), {
        method: "POST",
        body: { email, password },
      });
      setAccessToken(response.access_token);
      await fetchUser();
    } finally {
      loading.value = false;
    }
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true;
    try {
      const response = await $fetch<AuthResponse>(apiPath("/auth/login"), {
        method: "POST",
        body: { email, password },
      });
      setAccessToken(response.access_token);
      await fetchUser();
    } finally {
      loading.value = false;
    }
  }

  return {
    user,
    loading,
    isAuthenticated,
    fetchUser,
    register,
    login,
    clearAuth,
  };
});

export function getAuthErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "data" in error) {
    const detail = (error as { data?: { detail?: unknown } }).data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return fallback;
}
