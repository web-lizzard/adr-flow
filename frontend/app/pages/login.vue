<script setup lang="ts">
import { toTypedSchema } from "@vee-validate/zod";
import { useForm } from "vee-validate";
import { z } from "zod";
import { getAuthErrorMessage } from "@/stores/auth";

definePageMeta({
  layout: "auth",
  middleware: ["guest"],
});

const auth = useAuth();
const route = useRoute();

const formSchema = toTypedSchema(
  z.object({
    email: z.email("Enter a valid email address"),
    password: z.string().min(1, "Password is required"),
  }),
);

const form = useForm({
  validationSchema: formSchema,
  initialValues: {
    email: "",
    password: "",
  },
});

const submitError = ref<string | null>(null);

const onSubmit = form.handleSubmit(async (values) => {
  submitError.value = null;
  try {
    await auth.login(values.email, values.password);
    const redirect =
      typeof route.query.redirect === "string" ? route.query.redirect : null;
    await navigateTo(redirect ?? "/workspace");
  } catch (error) {
    submitError.value = getAuthErrorMessage(error, "Invalid email or password");
  }
});
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>Sign in</CardTitle>
      <CardDescription>
        Enter your email and password to access your workspace.
      </CardDescription>
    </CardHeader>
    <CardContent>
      <form class="space-y-4" @submit="onSubmit">
        <p
          v-if="submitError"
          class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {{ submitError }}
        </p>

        <FormField v-slot="{ componentField }" name="email">
          <FormItem>
            <FormLabel>Email</FormLabel>
            <FormControl>
              <Input
                type="email"
                autocomplete="email"
                placeholder="you@example.com"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="password">
          <FormItem>
            <FormLabel>Password</FormLabel>
            <FormControl>
              <Input
                type="password"
                autocomplete="current-password"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <Button class="w-full" type="submit" :disabled="auth.loading.value">
          {{ auth.loading.value ? "Signing in…" : "Sign in" }}
        </Button>
      </form>
    </CardContent>
    <CardFooter class="justify-center">
      <p class="text-sm text-muted-foreground">
        New here?
        <NuxtLink
          class="font-medium text-primary hover:underline"
          to="/register"
        >
          Create an account
        </NuxtLink>
      </p>
    </CardFooter>
  </Card>
</template>
