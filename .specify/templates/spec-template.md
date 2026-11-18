# Especificación de Funcionalidad: [NOMBRE DE LA FUNCIONALIDAD]

**Rama de funcionalidad**: `[NNN-nombre-corto]`

**Creado**: [FECHA]

**Estado**: Draft

**Entrada**: Descripción del usuario: "$ARGUMENTS"

## Escenarios de Usuario y Pruebas *(obligatorio)*

<!--
  IMPORTANTE: Las historias de usuario deben priorizarse como viajes del usuario
  ordenados por importancia. Cada historia debe poder probarse de forma
  INDEPENDIENTE: si se implementa solo una, debe entregar valor por sí misma.

  Asigna prioridades (P1, P2, P3, etc.), donde P1 es la más crítica.
  Cada historia debe poder desarrollarse, probarse, desplegarse y demostrarse
  de forma independiente.
-->

### Historia de Usuario 1 - [Título breve] (Prioridad: P1)

[Describir este viaje del usuario en lenguaje sencillo]

**Por qué esta prioridad**: [Explicar el valor y por qué tiene esta prioridad]

**Prueba independiente**: [Describir cómo puede probarse por separado, p. ej. «Se comprueba por completo al realizar [acción] y aporta [valor]»]

**Escenarios de aceptación**:

1. **Dado** [estado inicial], **cuando** [acción], **entonces** [resultado esperado]
2. **Dado** [estado inicial], **cuando** [acción], **entonces** [resultado esperado]

---

### Historia de Usuario 2 - [Título breve] (Prioridad: P2)

[Describir este viaje del usuario en lenguaje sencillo]

**Por qué esta prioridad**: [Explicar el valor y por qué tiene esta prioridad]

**Prueba independiente**: [Describir cómo puede probarse por separado]

**Escenarios de aceptación**:

1. **Dado** [estado inicial], **cuando** [acción], **entonces** [resultado esperado]

---

### Historia de Usuario 3 - [Título breve] (Prioridad: P3)

[Describir este viaje del usuario en lenguaje sencillo]

**Por qué esta prioridad**: [Explicar el valor y por qué tiene esta prioridad]

**Prueba independiente**: [Describir cómo puede probarse por separado]

**Escenarios de aceptación**:

1. **Dado** [estado inicial], **cuando** [acción], **entonces** [resultado esperado]

---

[Añadir más historias de usuario según sea necesario, cada una con su prioridad]

### Casos límite

<!--
  ACCIÓN REQUERIDA: Este contenido son marcadores de posición.
  Sustituirlos por los casos límite reales.
-->

- ¿Qué ocurre cuando [condición límite]?
- ¿Cómo gestiona el sistema [escenario de error]?

## Requisitos *(obligatorio)*

<!--
  ACCIÓN REQUERIDA: Este contenido son marcadores de posición.
  Sustituirlos por los requisitos funcionales reales.
  Convención: HUxx-RF-### para requisitos funcionales, HUxx-RN-## para reglas
  de negocio y HUxx-SC-### para criterios de éxito; xx es el número de la HU.
-->

### Requisitos Funcionales

- **HUxx-RF-001**: El sistema DEBE [capacidad concreta, p. ej. «permitir crear cuentas»]
- **HUxx-RF-002**: El sistema DEBE [validar los datos de entrada]
- **HUxx-RF-003**: Los usuarios DEBEN poder [interacción clave, p. ej. «restablecer su contraseña»]
- **HUxx-RF-004**: El sistema DEBE [requisito de datos, p. ej. «persistir las preferencias»]
- **HUxx-RF-005**: El sistema DEBE [comportamiento, p. ej. «registrar eventos de seguridad»]

*Ejemplo de marcado de un requisito ambiguo:*

- **HUxx-RF-006**: El sistema DEBE autenticar usuarios mediante [NEEDS CLARIFICATION: método no especificado: email/contraseña, SSO, OAuth...]
- **HUxx-RF-007**: El sistema DEBE conservar los datos del usuario durante [NEEDS CLARIFICATION: plazo de conservación no especificado]

### Entidades Clave *(incluir si la funcionalidad implica datos)*

- **[Entidad 1]**: [Qué representa, atributos principales sin detalles de implementación]
- **[Entidad 2]**: [Qué representa, relaciones con otras entidades]

## Criterios de Éxito *(obligatorio)*

<!--
  ACCIÓN REQUERIDA: Definir criterios de éxito medibles.
  Deben ser independientes de la tecnología y verificables.
-->

### Resultados Medibles

- **HUxx-SC-001**: [Métrica medible, p. ej. «Los usuarios completan el alta en menos de 2 minutos»]
- **HUxx-SC-002**: [Métrica medible, p. ej. «El sistema atiende 1000 usuarios concurrentes sin degradación»]
- **HUxx-SC-003**: [Métrica de usuario, p. ej. «El 90 % completa la tarea principal al primer intento»]
- **HUxx-SC-004**: [Métrica de negocio, p. ej. «Reducir un 50 % las incidencias relacionadas con [X]»]

## Supuestos

<!--
  ACCIÓN REQUERIDA: Este contenido son marcadores de posición.
  Completar con los supuestos y valores por defecto razonables elegidos cuando
  la descripción del usuario no especificó algún detalle.
-->

- [Supuesto sobre los usuarios, p. ej. «Los usuarios tienen conectividad estable»]
- [Supuesto sobre el alcance, p. ej. «El móvil nativo queda fuera de alcance en v1»]
- [Supuesto sobre datos/entorno, p. ej. «Se reutiliza la autenticación existente»]
- [Dependencia de otro sistema/servicio, p. ej. «Se requiere acceso al API de perfiles»]
