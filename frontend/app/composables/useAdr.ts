export function useAdr() {
  const store = useAdrStore();

  return {
    currentAdr: computed(() => store.currentAdr),
    adrs: computed(() => store.adrs),
    loading: computed(() => store.loading),
    listLoading: computed(() => store.listLoading),
    listError: computed(() => store.listError),
    isDirty: computed(() => store.isDirty),
    reviewAnnotations: computed(
      () => store.currentAdr?.reviewAnnotations ?? null,
    ),
    reviewedAt: computed(() => store.currentAdr?.reviewedAt ?? null),
    reviewError: computed(() => store.currentAdr?.reviewError ?? null),
    create: store.create,
    fetchList: store.fetchList,
    load: store.load,
    save: store.save,
    searchByTitle: store.searchByTitle,
    submitForReview: store.submitForReview,
    refreshReviewStatus: store.refreshReviewStatus,
    updateTitle: store.updateTitle,
    updateContent: store.updateContent,
  };
}
