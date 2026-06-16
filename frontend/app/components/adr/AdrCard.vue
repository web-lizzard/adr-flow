<script setup lang="ts">
import AdrStatusBadge from "@/components/adr/AdrStatusBadge.vue";
import Card from "@/components/ui/card/Card.vue";
import CardContent from "@/components/ui/card/CardContent.vue";
import CardHeader from "@/components/ui/card/CardHeader.vue";
import CardTitle from "@/components/ui/card/CardTitle.vue";
import { formatAdrDate } from "@/utils/formatAdrDate";

const props = defineProps<{
  id: string;
  title: string;
  status: string;
  updatedAt: string;
}>();

const formattedDate = computed(() => formatAdrDate(props.updatedAt));

function onClick() {
  void navigateTo(`/workspace/adr/${props.id}`);
}
</script>

<template>
  <Card
    class="cursor-pointer transition-colors hover:bg-accent/50"
    role="button"
    tabindex="0"
    @click="onClick"
    @keydown.enter="onClick"
    @keydown.space.prevent="onClick"
  >
    <CardHeader class="space-y-2">
      <div class="flex items-start justify-between gap-2">
        <CardTitle class="line-clamp-2 text-base">{{ title }}</CardTitle>
        <AdrStatusBadge :status="status" />
      </div>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">
        Last edited {{ formattedDate }}
      </p>
    </CardContent>
  </Card>
</template>
