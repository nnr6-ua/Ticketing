<script setup lang="ts">
import { ref } from "vue";
import AppHeader from "./components/AppHeader.vue";
import TicketConfirmation from "./components/TicketConfirmation.vue";
import TicketForm from "./components/TicketForm.vue";
import type { Ticket } from "./types/api";

const createdTicket = ref<Ticket | null>(null);

function handleCreated(ticket: Ticket) {
  createdTicket.value = ticket;
}

function reset() {
  createdTicket.value = null;
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <AppHeader />

    <main class="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <TicketConfirmation
        v-if="createdTicket"
        :ticket="createdTicket"
        @create-another="reset"
      />
      <TicketForm v-else @created="handleCreated" />
    </main>

    <footer class="mx-auto max-w-3xl px-4 pb-8 text-center text-xs text-slate-400 sm:px-6">
      Mesa de ayuda interna · v0.1
    </footer>
  </div>
</template>
