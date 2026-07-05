<script setup lang="ts">
const auth = useAuth();

onMounted(async () => {
  await auth.fetchUser();
  await navigateTo(auth.isAuthenticated.value ? "/workspace" : "/login");
});
</script>

<template>
  <div />
</template>
