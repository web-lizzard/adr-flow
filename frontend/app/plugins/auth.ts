export default defineNuxtPlugin(async () => {
  const auth = useAuthStore();
  if (!auth.user) {
    await auth.fetchUser();
  }
});
