export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) {
    return;
  }

  const auth = useAuthStore();

  if (!auth.user) {
    await auth.fetchUser();
  }

  if (auth.isAuthenticated) {
    return navigateTo("/workspace");
  }
});
