<script setup lang="ts">
import AdrStatusBadge from "@/components/adr/AdrStatusBadge.vue";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import Button from "@/components/ui/button/Button.vue";
import Card from "@/components/ui/card/Card.vue";
import CardContent from "@/components/ui/card/CardContent.vue";
import CardHeader from "@/components/ui/card/CardHeader.vue";
import CardTitle from "@/components/ui/card/CardTitle.vue";
import { formatAdrDate } from "@/utils/formatAdrDate";
import { Trash2 } from "@lucide/vue";

const props = defineProps<{
  id: string;
  title: string;
  status: string;
  updatedAt: string;
  removing?: boolean;
}>();

const emit = defineEmits<{
  remove: [id: string];
}>();

const formattedDate = computed(() => formatAdrDate(props.updatedAt));

function onClick() {
  void navigateTo(`/workspace/adr/${props.id}`);
}

function onConfirmRemove() {
  emit("remove", props.id);
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
        <div class="flex shrink-0 items-center gap-1">
          <div @click.stop>
            <AlertDialog>
              <AlertDialogTrigger as-child>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-8"
                  aria-label="Remove ADR"
                  :disabled="removing"
                >
                  <Trash2 class="size-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Remove ADR?</AlertDialogTitle>
                  <AlertDialogDescription>
                    "{{ title }}" will be removed from your workspace list. You
                    can still recover it from the database if needed.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction as-child>
                    <Button
                      data-testid="confirm-remove"
                      variant="destructive"
                      @click="onConfirmRemove"
                    >
                      Remove
                    </Button>
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
          <AdrStatusBadge :status="status" />
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">
        Last edited {{ formattedDate }}
      </p>
    </CardContent>
  </Card>
</template>
