<script setup lang="ts">
definePageMeta({
  layout: "auth",
});
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>Auth layout</CardTitle>
      <CardDescription>
        Centered card shell for login and registration pages.
      </CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="space-y-2">
        <Label for="preview-email">Email</Label>
        <Input id="preview-email" type="email" placeholder="you@example.com" />
      </div>
      <Button class="w-full">Preview button</Button>
    </CardContent>
    <CardFooter class="justify-center">
      <Button variant="link" as-child>
        <NuxtLink to="/">Back to home</NuxtLink>
      </Button>
    </CardFooter>
  </Card>
</template>
