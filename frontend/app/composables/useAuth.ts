export function useAuth() {
  const store = useAuthStore();

  return {
    user: computed(() => store.user),
    isAuthenticated: computed(() => store.isAuthenticated),
    loading: computed(() => store.loading),
    login: store.login,
    register: store.register,
    fetchUser: store.fetchUser,
  };
}
