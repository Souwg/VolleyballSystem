Alcance

Estas instrucciones aplican a todo SportFlow.

Antes de cambiar código, revisa la solicitud y los archivos relacionados.

Verifica los hechos en el repositorio. No inventes comandos, endpoints, modelos, variables ni reglas de negocio.

Usa como fuente de verdad: código y configuración, migraciones, docs/ y finalmente el README.md, que aún conserva partes del boilerplate de 4Geeks.

Haz cambios pequeños y enfocados. Conserva modificaciones ajenas a la tarea.

Proyecto

Frontend: React 16, React Router 6, Context/Flux, Webpack 5 y CSS propio en src/front/.

Backend: Flask, SQLAlchemy y Flask-Migrate en src/; la API se registra bajo /api.

Base de datos: DATABASE_URL; el devcontainer usa PostgreSQL y existe fallback local a SQLite.

Autenticación: JWT access/refresh. Roles observados: system_admin, club_owner, coach y staff.

PWA: public/manifest.webmanifest y public/service-worker.js.

Interfaz en español y con enfoque responsive/mobile-first.

Archivos principales:

src/app.py: configuración Flask, JWT, base de datos y errores globales.

src/api/models.py: modelos y serializadores.

src/api/routes.py: endpoints y lógica de negocio.

src/front/js/layout.js: rutas del frontend.

src/front/js/store/flux.js: estado y acciones.

src/front/js/utils/authFetch.js: sesión y respuestas HTTP.

src/front/js/utils/errorMessages.js: mensajes por código de error.

migrations/: migraciones de base de datos.

Comandos reales

El repositorio declara Node.js 16.x y Python 3.10.

npm ci
pipenv install
cp .env.example .env

pipenv run start # backend: 3001
npm run start # frontend: 3000
npm run build # build del frontend

pipenv run migrate
pipenv run upgrade

Revisa cada migración antes de aplicarla y usa únicamente una base local o de desarrollo claramente identificada.

No ejecutes reset_db, downgrade ni operaciones de producción sin autorización explícita.

No hay suite automatizada ni scripts test o lint en esta versión. No afirmes que existen o que fueron ejecutados.

Reglas de implementación

Backend

Protege rutas privadas con @jwt_required() y toma la identidad desde el JWT.

Recarga el usuario, valida cuenta activa y rol, y limita todos los datos del club al club_id autenticado. Un UUID conocido no concede acceso.

Conserva errores JSON con message, code estable y estado HTTP correcto. No expongas excepciones internas.

Al crear un código de error, actualiza errorMessages.js y, si corresponde a formulario, FORM_ERRORS en authFetch.js.

Valida antes de escribir; usa transacciones y rollback al manejar fallos.

Todo cambio de esquema requiere una migración. Conserva los campos esperados por los métodos serialize().

Frontend

Registra rutas en layout.js y estado compartido en las acciones de flux.js.

Usa authFetch y parseResponse para endpoints protegidos. Mantén el resultado normalizado { ok, data } o { ok: false, code, message }.

Usa REACT_APP_BACKEND_URL; no codifiques URLs de servidores en componentes.

Reutiliza componentes de src/front/js/component/ui/, estilos existentes y textos en español.

No edites manualmente public/bundle.js ni public/index.html; Webpack los genera.

Contratos críticos

Conserva el flujo: login → cambio de contraseña si first_login → onboarding para usuarios no administradores.

La autorización definitiva siempre debe estar en el backend, no solo en los guards de React.

No borres ni recalcules pagos o cargos pagados/con recibo sin una regla explícita.

Los números de recibo se generan en el backend mediante ReceiptCounter, por club y año; nunca en el navegador.

El service worker no debe cachear API, tokens, pagos ni información privada.

Seguridad y archivos

Nunca versionees .env, claves, credenciales, backups ni datos de producción. Documenta nuevas variables solo con valores seguros en .env.example.

No registres contraseñas, JWT, enlaces de recuperación ni datos personales.

public/uploads/ contiene archivos generados ya versionados; no lo tomes como patrón ni agregues nuevos uploads o recibos salvo petición expresa.

No uses comandos destructivos ni cambies GitHub, VPS, Docker, Cloudflare, Resend o la base de datos sin autorización.

Git y despliegue

Revisa git status --short antes y después de trabajar.

No hagas commit, push, merge, rebase o deploy salvo petición expresa.

Un push a develop activa .github/workflows/deploy.yml y ejecuta /opt/sportflow/deploy.sh. Trátalo como una posible modificación de producción aunque documentación antigua diga lo contrario.

Validación y entrega

Frontend: npm run build.

Python: python -m compileall src.

Modelos: revisar modelo y migración; aplicar solo en desarrollo seguro.

API/autenticación: comprobar éxito, ausencia de token, rol incorrecto, recurso de otro club y código de error.

Si algo no pudo comprobarse, dilo claramente.

Al finalizar, resume cambios, archivos modificados, validaciones, migraciones o variables nuevas y riesgos pendientes.
