import { computed, onMounted, ref } from "vue";
import { defineStore } from "pinia";

Object.assign(globalThis, {
  ref,
  computed,
  onMounted,
  defineStore,
});
