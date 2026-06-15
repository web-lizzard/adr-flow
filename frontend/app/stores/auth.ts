import { apiPath } from "../../composables/useApi";

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

  async function fetchUser(): Promise<boolean> {
    loading.value = true;
    try {
      const response = await $fetch<UserResponse>(apiPath("/auth/me"));
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
      const response = await $fetch<UserResponse>(apiPath("/auth/register"), {
        method: "POST",
        body: { email, password },
      });
      user.value = toAuthUser(response);
    } finally {
      loading.value = false;
    }
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true;
    try {
      const response = await $fetch<UserResponse>(apiPath("/auth/login"), {
        method: "POST",
        body: { email, password },
      });
      user.value = toAuthUser(response);
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
