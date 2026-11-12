import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  ApiError,
  createTicket,
  getPriorities,
  getSuggestion,
} from "../services/api";
import type { Priority, SuggestionResponse, Ticket } from "../types/api";

export function useTicketForm() {
  const priorities = ref<Priority[]>([]);
  const prioritiesLoading = ref(false);
  const prioritiesError = ref<string | null>(null);

  const title = ref("");
  const description = ref("");
  const priorityId = ref<number | null>(null);
  const priorityTouched = ref(false);
  const attachments = ref<File[]>([]);

  const suggestion = ref<SuggestionResponse | null>(null);
  const suggestionLoading = ref(false);
  const suggestionError = ref<string | null>(null);

  const submitting = ref(false);
  const errorMessage = ref<string | null>(null);
  const fieldErrors = ref<Record<string, string>>({});
  const showValidation = ref(false);

  const titleError = computed(() => {
    const length = title.value.trim().length;
    if (length === 0) return "Escribe un título para el ticket.";
    if (length < 5) return "El título debe tener al menos 5 caracteres.";
    if (length > 120) return "El título no puede superar los 120 caracteres.";
    return "";
  });

  const descriptionError = computed(() => {
    const length = description.value.trim().length;
    if (length === 0) return "Describe el problema o la solicitud.";
    if (length < 20) return "La descripción debe tener al menos 20 caracteres.";
    if (length > 5000) return "La descripción no puede superar los 5000 caracteres.";
    return "";
  });

  const isValid = computed(() => !titleError.value && !descriptionError.value);

  const titleFieldError = computed(
    () => fieldErrors.value.title ?? (showValidation.value ? titleError.value : ""),
  );
  const descriptionFieldError = computed(
    () =>
      fieldErrors.value.description ??
      (showValidation.value ? descriptionError.value : ""),
  );

  let suggestionTimer: ReturnType<typeof setTimeout> | undefined;
  let suggestionRequestId = 0;

  async function loadPriorities() {
    prioritiesLoading.value = true;
    prioritiesError.value = null;
    try {
      priorities.value = await getPriorities();
      if (priorityId.value === null) {
        const media = priorities.value.find((priority) => priority.name === "Media");
        priorityId.value = media?.id ?? priorities.value[0]?.id ?? null;
      }
    } catch {
      prioritiesError.value =
        "No se pudieron cargar las prioridades. Se usará la prioridad sugerida.";
    } finally {
      prioritiesLoading.value = false;
    }
  }

  async function loadSuggestion() {
    const requestId = ++suggestionRequestId;
    suggestionLoading.value = true;
    suggestionError.value = null;

    try {
      const result = await getSuggestion(title.value, description.value);
      if (requestId !== suggestionRequestId) return;
      suggestion.value = result;
      if (!priorityTouched.value) {
        priorityId.value = result.priority.id;
      }
    } catch {
      if (requestId !== suggestionRequestId) return;
      suggestionError.value =
        "No se pudo calcular la sugerencia. Puedes elegir la prioridad manualmente.";
    } finally {
      if (requestId === suggestionRequestId) {
        suggestionLoading.value = false;
      }
    }
  }

  function scheduleSuggestion() {
    if (suggestionTimer) clearTimeout(suggestionTimer);
    suggestionTimer = setTimeout(() => {
      void loadSuggestion();
    }, 400);
  }

  function setPriority(value: number | null) {
    priorityId.value = value;
    priorityTouched.value = true;
  }

  async function submit(): Promise<Ticket | null> {
    showValidation.value = true;
    errorMessage.value = null;
    fieldErrors.value = {};

    if (!isValid.value) {
      return null;
    }

    submitting.value = true;
    try {
      return await createTicket({
        title: title.value.trim(),
        description: description.value.trim(),
        priorityId: priorityId.value,
        attachments: attachments.value,
      });
    } catch (error) {
      if (error instanceof ApiError) {
        errorMessage.value = error.message;
        if (error.field) {
          fieldErrors.value = { [error.field]: error.message };
        }
      } else {
        errorMessage.value =
          "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
      }
      return null;
    } finally {
      submitting.value = false;
    }
  }

  function reset() {
    title.value = "";
    description.value = "";
    priorityId.value = null;
    priorityTouched.value = false;
    attachments.value = [];
    suggestion.value = null;
    suggestionError.value = null;
    submitting.value = false;
    errorMessage.value = null;
    fieldErrors.value = {};
    showValidation.value = false;
  }

  watch([title, description], scheduleSuggestion);
  onMounted(() => {
    void loadPriorities();
    void loadSuggestion();
  });
  onBeforeUnmount(() => {
    if (suggestionTimer) clearTimeout(suggestionTimer);
  });

  return {
    priorities,
    prioritiesLoading,
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
    fieldErrors,
    showValidation,
    titleError,
    descriptionError,
    titleFieldError,
    descriptionFieldError,
    isValid,
    setPriority,
    submit,
    reset,
    loadPriorities,
    loadSuggestion,
  };
}
