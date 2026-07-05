export default defineNuxtPlugin(async () => {
  if (import.meta.server) {
    return;
  }

  const auth = useAuthStore();
  if (!auth.user) {
    await auth.fetchUser();
  }
});
