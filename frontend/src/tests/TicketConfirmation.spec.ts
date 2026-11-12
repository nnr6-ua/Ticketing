import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import TicketConfirmation from "../components/TicketConfirmation.vue";
import type { Ticket } from "../types/api";

const ticket: Ticket = {
  id: 1,
  ticket_number: "TK-000001",
  title: "No funciona la VPN",
  description: "No puedo conectar desde ayer.",
  status: "Abierto",
  creator: { id: 1, name: "Empleado Demo", email: "demo@example.com" },
  category: { id: 1, name: "Red y conectividad" },
  priority: { id: 3, name: "Alta", level: 3, color: "#f59e0b" },
  attachments: [
    {
      id: 1,
      original_filename: "foto.png",
      mime_type: "image/png",
      size_bytes: 1024,
    },
  ],
  created_at: "2026-10-29T10:00:00Z",
  updated_at: "2026-10-29T10:00:00Z",
  duplicate: false,
};

describe("TicketConfirmation", () => {
  it("muestra los datos del ticket creado", () => {
    const wrapper = mount(TicketConfirmation, { props: { ticket } });

    expect(wrapper.text()).toContain("Ticket creado");
    expect(wrapper.text()).toContain("TK-000001");
    expect(wrapper.text()).toContain("Abierto");
    expect(wrapper.text()).toContain("Red y conectividad");
    expect(wrapper.text()).toContain("Alta");
    expect(wrapper.text()).toContain("foto.png");
    wrapper.unmount();
  });

  it("muestra el mensaje de duplicado", () => {
    const wrapper = mount(TicketConfirmation, {
      props: { ticket: { ...ticket, duplicate: true } },
    });

    expect(wrapper.text()).toContain("Ticket ya registrado");
    expect(wrapper.text()).toContain("Ya existía un ticket con este mismo contenido");
    wrapper.unmount();
  });

  it("copia el número y permite crear otro", async () => {
    const wrapper = mount(TicketConfirmation, { props: { ticket } });

    await wrapper.find("button").trigger("click");
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("TK-000001");

    const createAnother = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Crear otro ticket"));
    await createAnother?.trigger("click");
    expect(wrapper.emitted("create-another")).toBeTruthy();
    wrapper.unmount();
  });
});
