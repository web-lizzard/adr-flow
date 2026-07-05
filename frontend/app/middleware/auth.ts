export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) {
    return;
  }

  const auth = useAuthStore();

  if (!auth.user) {
    const authenticated = await auth.fetchUser();
    if (!authenticated) {
      return navigateTo("/login");
    }
  }
});
