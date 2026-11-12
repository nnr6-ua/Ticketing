<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from "vue";
import { PaperClipIcon, XMarkIcon } from "@heroicons/vue/20/solid";

const props = withDefaults(
  defineProps<{
    modelValue: File[];
    maxFiles?: number;
    maxSize?: number;
  }>(),
  {
    maxFiles: 5,
    maxSize: 5 * 1024 * 1024,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: File[]];
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const errors = ref<string[]>([]);
const isDragging = ref(false);
const previews = reactive(new Map<File, string>());

const allowedExtensions = new Set(["png", "jpg", "jpeg", "gif"]);
const allowedTypes = new Set(["image/png", "image/jpeg", "image/gif"]);

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isAllowed(file: File): boolean {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const extensionOk = allowedExtensions.has(extension);
  const typeOk = file.type === "" || allowedTypes.has(file.type);
  return extensionOk && typeOk;
}

function openPicker() {
  fileInput.value?.click();
}

function addFiles(files: FileList | File[]) {
  const incoming = Array.from(files);
  const nextErrors: string[] = [];
  const accepted: File[] = [];

  for (const file of incoming) {
    if (!isAllowed(file)) {
      nextErrors.push(`${file.name}: solo se permiten imágenes PNG, JPG o GIF.`);
      continue;
    }
    if (file.size > props.maxSize) {
      nextErrors.push(`${file.name}: supera el límite de 5 MB.`);
      continue;
    }
    if (props.modelValue.length + accepted.length >= props.maxFiles) {
      nextErrors.push(`Puedes adjuntar como máximo ${props.maxFiles} archivos.`);
      break;
    }
    const duplicated =
      props.modelValue.some(
        (current) =>
          current.name === file.name &&
          current.size === file.size &&
          current.lastModified === file.lastModified,
      ) ||
      accepted.some(
        (current) =>
          current.name === file.name &&
          current.size === file.size &&
          current.lastModified === file.lastModified,
      );
    if (duplicated) {
      nextErrors.push(`${file.name}: ya está adjunto.`);
      continue;
    }
    accepted.push(file);
  }

  errors.value = nextErrors;
  if (accepted.length > 0) {
    emit("update:modelValue", [...props.modelValue, ...accepted]);
  }
}

function handleInput(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files) addFiles(input.files);
  input.value = "";
}

function handleDrop(event: DragEvent) {
  isDragging.value = false;
  if (event.dataTransfer?.files) addFiles(event.dataTransfer.files);
}

function removeFile(index: number) {
  emit(
    "update:modelValue",
    props.modelValue.filter((_, current) => current !== index),
  );
}

watch(
  () => props.modelValue,
  (files) => {
    for (const [file, url] of previews) {
      if (!files.includes(file)) {
        URL.revokeObjectURL(url);
        previews.delete(file);
      }
    }
    for (const file of files) {
      if (!previews.has(file)) {
        previews.set(file, URL.createObjectURL(file));
      }
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  for (const url of previews.values()) {
    URL.revokeObjectURL(url);
  }
  previews.clear();
});
</script>

<template>
  <div>
    <div class="flex items-center justify-between gap-3">
      <label class="text-sm font-medium text-slate-900">Adjuntos</label>
      <span class="text-xs text-slate-500">
        Máx. {{ maxFiles }} archivos · {{ formatSize(maxSize) }} cada uno
      </span>
    </div>

    <button
      type="button"
      class="mt-2 flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition"
      :class="
        isDragging
          ? 'border-sky-400 bg-sky-50'
          : 'border-slate-300 bg-white hover:border-sky-400 hover:bg-sky-50/40'
      "
      @click="openPicker"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <PaperClipIcon class="h-6 w-6 text-slate-400" aria-hidden="true" />
      <span class="text-sm font-medium text-slate-700">
        Arrastra imágenes aquí o haz clic para seleccionarlas
      </span>
      <span class="text-xs text-slate-500">PNG, JPG o GIF · opcional</span>
    </button>

    <input
      ref="fileInput"
      type="file"
      class="sr-only"
      accept="image/png,image/jpeg,image/gif"
      multiple
      @change="handleInput"
    />

    <ul v-if="modelValue.length > 0" class="mt-3 space-y-2">
      <li
        v-for="(file, index) in modelValue"
        :key="`${file.name}-${file.lastModified}`"
        class="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2"
      >
        <img
          :src="previews.get(file)"
          alt=""
          class="h-12 w-12 flex-none rounded-lg object-cover"
        />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-slate-900">{{ file.name }}</p>
          <p class="text-xs text-slate-500">{{ formatSize(file.size) }}</p>
        </div>
        <button
          type="button"
          class="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
          :aria-label="`Quitar ${file.name}`"
          @click="removeFile(index)"
        >
          <XMarkIcon class="h-4 w-4" aria-hidden="true" />
        </button>
      </li>
    </ul>

    <ul v-if="errors.length > 0" class="mt-2 space-y-1" role="alert">
      <li v-for="error in errors" :key="error" class="text-xs text-rose-600">
        {{ error }}
      </li>
    </ul>
  </div>
</template>
