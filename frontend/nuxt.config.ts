import tailwindcss from "@tailwindcss/vite";

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  css: ["~/assets/css/main.css"],

  modules: ["@pinia/nuxt", "shadcn-nuxt", "@nuxtjs/color-mode"],

  colorMode: {
    classSuffix: "",
    preference: "system",
    fallback: "light",
  },

  shadcn: {
    prefix: "",
    componentDir: "@/components/ui",
  },

  vite: {
    plugins: [tailwindcss()],
  },

  nitro: {
    preset: "node-server",
  },

  runtimeConfig: {
    /** Backend origin for Nitro proxy (Cloud Run: NUXT_API_UPSTREAM). */
    apiUpstream: "http://127.0.0.1:8000",
    public: {
      apiBase: "/api",
    },
  },
});
