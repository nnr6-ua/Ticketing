import { afterEach } from 'vitest'

import { config } from '@vue/test-utils'

// Cada prueba monta y desmonta sus propios componentes; se limpia el DOM para
// que no queden nodos ni listeners entre casos.
afterEach(() => {
  document.body.innerHTML = ''
})

// Silencia el aviso de Vue sobre componentes no registrados que no aplican a
// estas pruebas unitarias (por ejemplo, iconos de lucide en stubs parciales).
config.global.config.warnHandler = () => {}
