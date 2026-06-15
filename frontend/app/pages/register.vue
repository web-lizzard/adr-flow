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

const formSchema = toTypedSchema(
  z
    .object({
      email: z.email("Enter a valid email address"),
      password: z.string().min(8, "Password must be at least 8 characters"),
      confirmPassword: z.string().min(1, "Confirm your password"),
    })
    .refine((values) => values.password === values.confirmPassword, {
      message: "Passwords do not match",
      path: ["confirmPassword"],
    }),
);

const form = useForm({
  validationSchema: formSchema,
  initialValues: {
    email: "",
    password: "",
    confirmPassword: "",
  },
});

const submitError = ref<string | null>(null);

const onSubmit = form.handleSubmit(async (values) => {
  submitError.value = null;
  try {
    await auth.register(values.email, values.password);
    await navigateTo("/workspace");
  } catch (error) {
    submitError.value = getAuthErrorMessage(
      error,
      "Unable to create account with the provided credentials",
    );
  }
});
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>Create an account</CardTitle>
      <CardDescription>
        Register with your email and a password of at least 8 characters.
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
                autocomplete="new-password"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="confirmPassword">
          <FormItem>
            <FormLabel>Confirm password</FormLabel>
            <FormControl>
              <Input
                type="password"
                autocomplete="new-password"
                v-bind="componentField"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <Button class="w-full" type="submit" :disabled="auth.loading.value">
          {{ auth.loading.value ? "Creating account…" : "Create account" }}
        </Button>
      </form>
    </CardContent>
    <CardFooter class="justify-center">
      <p class="text-sm text-muted-foreground">
        Already have an account?
        <NuxtLink class="font-medium text-primary hover:underline" to="/login">
          Sign in
        </NuxtLink>
      </p>
    </CardFooter>
  </Card>
</template>
