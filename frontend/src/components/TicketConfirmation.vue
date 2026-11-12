<script setup lang="ts">
import { computed, ref } from "vue";
import {
  ArrowPathIcon,
  CheckCircleIcon,
  ClipboardDocumentIcon,
  InformationCircleIcon,
  PaperClipIcon,
} from "@heroicons/vue/24/outline";
import type { Ticket } from "../types/api";

const props = defineProps<{ ticket: Ticket }>();
const emit = defineEmits<{ "create-another": [] }>();

const copied = ref(false);

const createdAt = computed(() =>
  new Intl.DateTimeFormat("es-ES", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(props.ticket.created_at)),
);

const title = computed(() =>
  props.ticket.duplicate ? "Ticket ya registrado" : "Ticket creado",
);

const description = computed(() =>
  props.ticket.duplicate
    ? "Ya existía un ticket con este mismo contenido. Te mostramos su referencia para que puedas seguir su estado."
    : "Hemos recibido tu solicitud. El equipo de soporte la revisará y te responderá por los canales habituales.",
);

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function copyNumber() {
  try {
    await navigator.clipboard.writeText(props.ticket.ticket_number);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    copied.value = false;
  }
}
</script>

<template>
  <section
    class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    aria-live="polite"
  >
    <div class="px-6 py-8 sm:px-8">
      <div
        class="grid h-14 w-14 place-items-center rounded-2xl"
        :class="ticket.duplicate ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'"
      >
        <InformationCircleIcon v-if="ticket.duplicate" class="h-8 w-8" aria-hidden="true" />
        <CheckCircleIcon v-else class="h-8 w-8" aria-hidden="true" />
      </div>

      <h1 class="mt-5 text-2xl font-semibold tracking-tight text-slate-900">
        {{ title }}
      </h1>
      <p class="mt-2 max-w-xl text-sm text-slate-600">{{ description }}</p>

      <div class="mt-6 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-slate-500">
            Número de ticket
          </p>
          <p class="mt-1 font-mono text-2xl font-semibold tracking-tight text-slate-900">
            {{ ticket.ticket_number }}
          </p>
        </div>
        <button
          type="button"
          class="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          @click="copyNumber"
        >
          <ClipboardDocumentIcon class="h-4 w-4" aria-hidden="true" />
          {{ copied ? "Copiado" : "Copiar número" }}
        </button>
      </div>

      <dl class="mt-6 grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Estado</dt>
          <dd class="mt-1 font-medium text-slate-900">{{ ticket.status }}</dd>
        </div>
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Categoría</dt>
          <dd class="mt-1 font-medium text-slate-900">{{ ticket.category.name }}</dd>
        </div>
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Prioridad</dt>
          <dd class="mt-1 flex items-center gap-2 font-medium text-slate-900">
            <span
              class="h-2.5 w-2.5 rounded-full"
              :style="{ backgroundColor: ticket.priority.color }"
            />
            {{ ticket.priority.name }}
          </dd>
        </div>
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Creador</dt>
          <dd class="mt-1 font-medium text-slate-900">{{ ticket.creator.name }}</dd>
        </div>
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Creado</dt>
          <dd class="mt-1 font-medium text-slate-900">{{ createdAt }}</dd>
        </div>
      </dl>

      <div v-if="ticket.attachments.length > 0" class="mt-6">
        <p class="text-xs font-medium uppercase tracking-wide text-slate-500">Adjuntos</p>
        <ul class="mt-2 space-y-2">
          <li
            v-for="attachment in ticket.attachments"
            :key="attachment.id"
            class="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2"
          >
            <PaperClipIcon class="h-4 w-4 flex-none text-slate-400" aria-hidden="true" />
            <span class="min-w-0 flex-1 truncate text-sm text-slate-700">
              {{ attachment.original_filename }}
            </span>
            <span class="flex-none text-xs text-slate-500">
              {{ formatSize(attachment.size_bytes) }}
            </span>
          </li>
        </ul>
      </div>

      <div class="mt-8 border-t border-slate-200 pt-6">
        <button
          type="button"
          class="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700"
          @click="emit('create-another')"
        >
          <ArrowPathIcon class="h-4 w-4" aria-hidden="true" />
          Crear otro ticket
        </button>
      </div>
    </div>
  </section>
</template>
