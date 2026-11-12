import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import AttachmentField from "../components/AttachmentField.vue";

function makeFile(name: string, type = "image/png", size = 10): File {
  return new File([new Uint8Array(size)], name, { type, lastModified: 1 });
}

function selectFiles(wrapper: ReturnType<typeof mount>, files: File[]) {
  const input = wrapper.find('input[type="file"]');
  Object.defineProperty(input.element, "files", {
    configurable: true,
    value: files,
  });
  return input.trigger("change");
}

describe("AttachmentField", () => {
  it("añade una imagen válida", async () => {
    const wrapper = mount(AttachmentField, { props: { modelValue: [] } });
    const file = makeFile("foto.png");

    await selectFiles(wrapper, [file]);
    await nextTick();

    expect(wrapper.emitted("update:modelValue")?.[0]?.[0]).toEqual([file]);
    wrapper.unmount();
  });

  it("rechaza archivos que no son imágenes", async () => {
    const wrapper = mount(AttachmentField, { props: { modelValue: [] } });

    await selectFiles(wrapper, [makeFile("notas.txt", "text/plain")]);
    await nextTick();

    expect(wrapper.text()).toContain("solo se permiten imágenes PNG, JPG o GIF");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    wrapper.unmount();
  });

  it("rechaza más de cinco archivos", async () => {
    const existing = Array.from({ length: 5 }, (_, index) => makeFile(`foto${index}.png`));
    const wrapper = mount(AttachmentField, { props: { modelValue: existing } });

    await selectFiles(wrapper, [makeFile("extra.png")]);
    await nextTick();

    expect(wrapper.text()).toContain("máximo 5 archivos");
    wrapper.unmount();
  });

  it("quita un archivo existente", async () => {
    const file = makeFile("foto.png");
    const wrapper = mount(AttachmentField, { props: { modelValue: [file] } });

    await wrapper.find('button[aria-label="Quitar foto.png"]').trigger("click");

    expect(wrapper.emitted("update:modelValue")?.[0]?.[0]).toEqual([]);
    wrapper.unmount();
  });
});
