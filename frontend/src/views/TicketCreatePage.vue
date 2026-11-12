<script setup lang="ts">
import { ref } from "vue";
import { RouterLink } from "vue-router";

import TicketConfirmation from "@/components/TicketConfirmation.vue";
import TicketForm from "@/components/TicketForm.vue";
import type { Ticket } from "@/types/api";

const createdTicket = ref<Ticket | null>(null);

function handleCreated(ticket: Ticket) {
  createdTicket.value = ticket;
}

function reset() {
  createdTicket.value = null;
}
</script>

<template>
  <main class="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
    <nav class="mb-6">
      <RouterLink
        to="/cola-de-trabajo"
        class="text-sm font-medium text-sky-700 hover:text-sky-900"
      >
        ← Volver a la cola de trabajo
      </RouterLink>
    </nav>

    <TicketConfirmation
      v-if="createdTicket"
      :ticket="createdTicket"
      @create-another="reset"
    />
    <TicketForm v-else @created="handleCreated" />

    <footer class="mt-8 text-center text-xs text-slate-400">
      Mesa de ayuda interna · v0.1
    </footer>
  </main>
</template>
