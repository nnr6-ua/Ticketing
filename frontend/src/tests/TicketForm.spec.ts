import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TicketForm from "../components/TicketForm.vue";
import { ApiError, createTicket, getPriorities, getSuggestion } from "../services/api";
import type { Priority, SuggestionResponse, Ticket } from "../types/api";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    getPriorities: vi.fn(),
    getSuggestion: vi.fn(),
    createTicket: vi.fn(),
  };
});

const priorities: Priority[] = [
  { id: 1, name: "Baja", level: 1, color: "#64748b" },
  { id: 2, name: "Media", level: 2, color: "#0ea5e9" },
  { id: 3, name: "Alta", level: 3, color: "#f59e0b" },
];

const suggestion: SuggestionResponse = {
  category: { id: 1, name: "Red y conectividad" },
  priority: priorities[2],
  category_is_fallback: false,
  priority_is_fallback: false,
};

const ticket: Ticket = {
  id: 1,
  ticket_number: "TK-000001",
  title: "No funciona la VPN",
  description: "No puedo conectar desde ayer.",
  status: "Abierto",
  creator: { id: 1, name: "Empleado Demo", email: "demo@example.com" },
  category: { id: 1, name: "Red y conectividad" },
  priority: priorities[2],
  attachments: [],
  created_at: "2026-10-29T10:00:00Z",
  updated_at: "2026-10-29T10:00:00Z",
  duplicate: false,
};

async function mountForm() {
  const wrapper = mount(TicketForm, { attachTo: document.body });
  await flushPromises();
  return wrapper;
}

async function fillForm(wrapper: Awaited<ReturnType<typeof mountForm>>) {
  await wrapper.find("#title").setValue("No funciona la VPN");
  await wrapper.find("#description").setValue("No puedo conectar desde ayer.");
}

describe("TicketForm", () => {
  beforeEach(() => {
    vi.mocked(getPriorities).mockResolvedValue(priorities);
    vi.mocked(getSuggestion).mockResolvedValue(suggestion);
    vi.mocked(createTicket).mockReset();
  });

  it("muestra errores de validación al enviar vacío", async () => {
    const wrapper = await mountForm();

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Escribe un título para el ticket.");
    expect(wrapper.text()).toContain("Describe el problema o la solicitud.");
    expect(createTicket).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("envía el ticket y emite created", async () => {
    vi.mocked(createTicket).mockResolvedValue(ticket);
    const wrapper = await mountForm();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(createTicket).toHaveBeenCalledWith({
      title: "No funciona la VPN",
      description: "No puedo conectar desde ayer.",
      priorityId: 3,
      attachments: [],
    });
    expect(wrapper.emitted("created")?.[0]?.[0]).toEqual(ticket);
    wrapper.unmount();
  });

  it("muestra el error cuando la identidad no está disponible", async () => {
    vi.mocked(createTicket).mockRejectedValue(
      new ApiError(401, {
        error: {
          code: "auth_required",
          message: "Falta la cabecera X-Employee-Id.",
        },
      }),
    );
    const wrapper = await mountForm();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Falta la cabecera X-Employee-Id.");
    wrapper.unmount();
  });

  it("permite reintentar tras un fallo sin perder los datos", async () => {
    vi.mocked(createTicket)
      .mockRejectedValueOnce(
        new ApiError(500, {
          error: { code: "server_error", message: "Fallo temporal." },
        }),
      )
      .mockResolvedValueOnce(ticket);
    const wrapper = await mountForm();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Fallo temporal.");

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(createTicket).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted("created")?.[0]?.[0]).toEqual(ticket);
    wrapper.unmount();
  });

  it("muestra el error del servidor y conserva los datos", async () => {
    vi.mocked(createTicket).mockRejectedValue(
      new ApiError(500, {
        error: { code: "SERVER_ERROR", message: "Fallo del servidor." },
      }),
    );
    const wrapper = await mountForm();
    await fillForm(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Fallo del servidor.");
    expect((wrapper.find("#title").element as HTMLInputElement).value).toBe(
      "No funciona la VPN",
    );
    wrapper.unmount();
  });
});
