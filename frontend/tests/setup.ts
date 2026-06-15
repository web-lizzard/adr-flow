import { computed, ref } from "vue";
import { defineStore } from "pinia";

Object.assign(globalThis, {
  ref,
  computed,
  defineStore,
});
