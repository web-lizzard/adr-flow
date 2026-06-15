export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuthStore();

  if (!auth.user) {
    const authenticated = await auth.fetchUser();
    if (!authenticated) {
      return navigateTo("/login");
    }
  }
});
