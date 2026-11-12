<script setup lang="ts">
import { useTicketForm } from "../composables/useTicketForm";
import type { Ticket } from "../types/api";
import AttachmentField from "./AttachmentField.vue";
import ErrorBanner from "./ErrorBanner.vue";
import SuggestionPanel from "./SuggestionPanel.vue";
import SpinnerIcon from "./icons/SpinnerIcon.vue";

const emit = defineEmits<{
  created: [ticket: Ticket];
}>();

const {
  priorities,
  prioritiesError,
  title,
  description,
  priorityId,
  attachments,
  suggestion,
  suggestionLoading,
  suggestionError,
  submitting,
  errorMessage,
  titleFieldError,
  descriptionFieldError,
  setPriority,
  submit,
} = useTicketForm();

async function handleSubmit() {
  const ticket = await submit();
  if (ticket) {
    emit("created", ticket);
  }
}
</script>

<template>
  <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="border-b border-slate-200 bg-gradient-to-r from-sky-50 to-white px-6 py-6 sm:px-8">
      <p class="text-xs font-semibold uppercase tracking-wider text-sky-700">
        Nueva incidencia
      </p>
      <h1 class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
        Crear un ticket
      </h1>
      <p class="mt-2 max-w-xl text-sm text-slate-600">
        Cuéntanos qué necesitas y el equipo de soporte se pondrá en marcha.
        La categoría se asigna automáticamente.
      </p>
    </div>

    <form class="space-y-6 px-6 py-6 sm:px-8" novalidate @submit.prevent="handleSubmit">
      <ErrorBanner :message="errorMessage" />

      <div>
        <label for="title" class="text-sm font-medium text-slate-900">
          Título <span class="text-sky-600">*</span>
        </label>
        <input
          id="title"
          v-model="title"
          type="text"
          maxlength="120"
          autocomplete="off"
          placeholder="Ej.: No funciona la VPN"
          class="mt-1 w-full rounded-xl border bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          :class="titleFieldError ? 'border-rose-400' : 'border-slate-300'"
          :aria-invalid="Boolean(titleFieldError)"
          aria-describedby="title-help title-error"
        />
        <div class="mt-1 flex items-start justify-between gap-3">
          <p id="title-help" class="text-xs text-slate-500">
            Resume el problema en una frase.
          </p>
          <p class="flex-none text-xs text-slate-400">{{ title.trim().length }}/120</p>
        </div>
        <p v-if="titleFieldError" id="title-error" role="alert" class="mt-1 text-sm text-rose-600">
          {{ titleFieldError }}
        </p>
      </div>

      <div>
        <label for="description" class="text-sm font-medium text-slate-900">
          Descripción <span class="text-sky-600">*</span>
        </label>
        <textarea
          id="description"
          v-model="description"
          rows="6"
          maxlength="5000"
          placeholder="Describe qué ocurre, desde cuándo y qué has probado."
          class="mt-1 w-full resize-y rounded-xl border bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          :class="descriptionFieldError ? 'border-rose-400' : 'border-slate-300'"
          :aria-invalid="Boolean(descriptionFieldError)"
          aria-describedby="description-help description-error"
        />
        <div class="mt-1 flex items-start justify-between gap-3">
          <p id="description-help" class="text-xs text-slate-500">
            Incluye los detalles que ayuden a reproducir el problema.
          </p>
          <p class="flex-none text-xs text-slate-400">
            {{ description.trim().length }}/5000
          </p>
        </div>
        <p
          v-if="descriptionFieldError"
          id="description-error"
          role="alert"
          class="mt-1 text-sm text-rose-600"
        >
          {{ descriptionFieldError }}
        </p>
      </div>

      <SuggestionPanel
        :suggestion="suggestion"
        :loading="suggestionLoading"
        :error="suggestionError"
        :priorities="priorities"
        :priority-id="priorityId"
        @update:priority-id="setPriority"
      />

      <p v-if="prioritiesError" class="text-xs text-amber-700">{{ prioritiesError }}</p>

      <AttachmentField v-model="attachments" />

      <div class="flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-xs text-slate-500">
          Los campos marcados con <span class="text-sky-600">*</span> son obligatorios.
        </p>
        <button
          type="submit"
          :disabled="submitting"
          class="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <SpinnerIcon v-if="submitting" class="h-4 w-4" />
          <span>{{ submitting ? "Creando ticket…" : "Crear ticket" }}</span>
        </button>
      </div>
    </form>
  </section>
</template>
