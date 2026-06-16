export function useAdr() {
  const store = useAdrStore();

  return {
    currentAdr: computed(() => store.currentAdr),
    adrs: computed(() => store.adrs),
    loading: computed(() => store.loading),
    listLoading: computed(() => store.listLoading),
    listError: computed(() => store.listError),
    isDirty: computed(() => store.isDirty),
    create: store.create,
    fetchList: store.fetchList,
    load: store.load,
    save: store.save,
    searchByTitle: store.searchByTitle,
    updateTitle: store.updateTitle,
    updateContent: store.updateContent,
  };
}
