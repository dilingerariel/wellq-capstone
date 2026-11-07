# Reglas permanentes del portal WellQ

- Evolucionar esta aplicación; conservar identidad visual, contratos FastAPI y documentos académicos.
- Cada función debe reorganizarse en móvil, tablet y escritorio. Verificar 320, 360, 375, 390, 430, 768, 1024, 1280, 1440 y 1920 px, tamaños intermedios, orientación horizontal, teclado, tacto y reflow equivalente al 200 %. Apuntar a WCAG 2.2 AA sin afirmar certificación automática.
- La pérdida de red no debe borrar formularios en memoria, ocultar datos recibidos de la sesión ni simular confirmación o sincronización. Mostrar sus límites y revalidar identidad antes de nuevas consultas al reconectar.
- No firmar JWT, fabricar login, ampliar roles ni persistir tokens/datos clínicos en localStorage, IndexedDB, CacheStorage o service workers. La autorización definitiva pertenece al servidor.
- El service worker solo puede cachear la lista pública de recursos del build. No cachear respuestas API, URLs con identificadores, notas, documentos, PDFs ni credenciales. Actualizaciones que recarguen requieren una acción explícita para no perder trabajo.
- No habilitar colas durables ni replay automático de mutaciones clínicas sin política aprobada de cifrado, claves, retención, permisos, idempotencia y conflictos. Mantener API y demo separados, sin fallback a datos falsos.
- Sesiones, formularios y cachés autenticadas permanecen en memoria y se limpian al cambiar identidad/permisos, cerrar sesión o expirar. Cancelar peticiones obsoletas y rechazar resultados tardíos.
- Mantener Flutter + Drift como cliente independiente para almacenamiento privado y cola durable móvil.
- Ejecutar typecheck, lint, formato, tests, build, controles de seguridad de cambios y pruebas de navegador aplicables. Instalar dependencias antes de iniciar servidores para evitar archivos bloqueados en Windows. No atribuir a un proveedor real pruebas ejecutadas con dobles.
