import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SuggestionPanel from "../components/SuggestionPanel.vue";
import type { Priority, SuggestionResponse } from "../types/api";

const priorities: Priority[] = [
  { id: 1, name: "Baja", level: 1, color: "#64748b" },
  { id: 2, name: "Media", level: 2, color: "#0ea5e9" },
  { id: 3, name: "Alta", level: 3, color: "#f59e0b" },
];

const suggestion: SuggestionResponse = {
  category: { id: 1, name: "Software" },
  priority: priorities[1],
  category_is_fallback: false,
  priority_is_fallback: false,
};

describe("SuggestionPanel", () => {
  it("muestra la categoría fija y la prioridad sugerida", () => {
    const wrapper = mount(SuggestionPanel, {
      props: {
        suggestion,
        loading: false,
        error: null,
        priorities,
        priorityId: 2,
      },
    });

    expect(wrapper.text()).toContain("Software");
    expect(wrapper.text()).toContain("Media");
    wrapper.unmount();
  });

  it("indica cuándo se usan valores por defecto", () => {
    const wrapper = mount(SuggestionPanel, {
      props: {
        suggestion: {
          ...suggestion,
          category_is_fallback: true,
          priority_is_fallback: true,
        },
        loading: false,
        error: null,
        priorities,
        priorityId: 2,
      },
    });

    expect(wrapper.text()).toContain("Se usará la categoría por defecto.");
    expect(wrapper.text()).toContain("Prioridad por defecto");
    wrapper.unmount();
  });
});
