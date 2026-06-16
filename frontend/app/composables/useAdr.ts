export function useAdr() {
  const store = useAdrStore();

  return {
    currentAdr: computed(() => store.currentAdr),
    loading: computed(() => store.loading),
    isDirty: computed(() => store.isDirty),
    create: store.create,
    load: store.load,
    save: store.save,
    searchByTitle: store.searchByTitle,
    updateTitle: store.updateTitle,
    updateContent: store.updateContent,
  };
}
