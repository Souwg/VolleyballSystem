# GitHub

> **Nivel:** Desarrollo
>
> **Audiencia:** Desarrolladores

---

## 1. Objetivo

GitHub es la plataforma utilizada para el control de versiones del código fuente de SportFlow.

Su función es mantener un historial de cambios, facilitar el trabajo colaborativo y servir como repositorio central del proyecto.

Actualmente GitHub también almacena la documentación técnica y será utilizado en el futuro para automatizar los despliegues mediante GitHub Actions.

---

## 2. Descripción general

El repositorio principal contiene todo el código fuente de SportFlow.

Actualmente se versionan:

- Backend.
- Frontend.
- Migraciones.
- Documentación.
- Configuración Docker.
- Scripts del proyecto.

No se versionan:

- Variables de entorno.
- Archivos temporales.
- Backups.
- Datos de producción.
- Archivos sensibles.

---

## 3. Flujo de trabajo

Actualmente el desarrollo sigue el siguiente proceso:

```
Desarrollador

      │

Modificar código

      │

Pruebas locales

      │

git add

      │

git commit

      │

git push origin develop

      │

GitHub

      │

Servidor VPS

      │

/opt/sportflow/deploy.sh
```

Todo cambio debe probarse localmente antes de ser enviado al repositorio.

---

## 4. Rama principal de desarrollo

Actualmente el proyecto utiliza:

```
develop
```

Todos los cambios son integrados primero en esta rama.

Una vez validados pueden desplegarse al servidor de producción.

---

## 5. Flujo de despliegue

El procedimiento oficial de despliegue es:

### 1. Actualizar el repositorio local

```bash
git checkout develop

git pull origin develop
```

---

### 2. Realizar cambios

Modificar el código.

Realizar pruebas.

---

### 3. Confirmar cambios

```bash
git add .

git commit -m "Descripción del cambio"
```

---

### 4. Enviar cambios

```bash
git push origin develop
```

---

### 5. Desplegar

Conectarse al servidor.

Ejecutar:

```bash
/opt/sportflow/deploy.sh
```

---

## 6. Commits

Se recomienda utilizar mensajes descriptivos.

Ejemplos:

```
Add payment receipt generation

Fix login validation

Improve dashboard performance

Add PWA support
```

Evitar mensajes poco descriptivos como:

```
Cambios

Fix

Update

Prueba
```

---

## 7. Documentación

Toda modificación importante en la infraestructura debe reflejarse también dentro del directorio:

```text
docs/
```

Esto garantiza que la documentación permanezca sincronizada con el estado real del proyecto.

---

## 8. GitHub Actions

Actualmente existe un workflow preparado para automatizar los despliegues.

Estado actual:

```
Pendiente
```

La activación quedó pospuesta debido a restricciones de facturación de GitHub relacionadas con los secretos necesarios para el despliegue.

Mientras tanto, el despliegue se realiza manualmente mediante:

```text
/opt/sportflow/deploy.sh
```

---

## 9. Buenas prácticas

Se recomienda:

- Trabajar siempre sobre la rama `develop`.
- Actualizar la rama antes de comenzar a desarrollar.
- Probar todos los cambios localmente.
- Utilizar mensajes de commit claros.
- Mantener sincronizada la documentación.
- Evitar realizar cambios directamente en producción.

---

## 10. Troubleshooting

### El push es rechazado

Verificar:

- Que la rama local esté actualizada.
- Si existen commits nuevos en GitHub.
- Si es necesario realizar un `git pull` o un `git rebase`.

---

### Conflictos durante un rebase

Revisar los archivos en conflicto.

Resolver los cambios.

Continuar el proceso:

```bash
git rebase --continue
```

---

### El despliegue no refleja los cambios

Verificar:

- Que el `git push` haya finalizado correctamente.
- Que `deploy.sh` se haya ejecutado en el VPS.
- Que Docker haya reconstruido la aplicación.

---

## 11. Checklist

Antes de desplegar verificar:

- Rama correcta.
- Repositorio actualizado.
- Código probado.
- Commit realizado.
- Push completado.
- Documentación actualizada.

---

## 12. Estado actual

| Componente | Estado |
|------------|--------|
| GitHub | ✅ |
| Rama develop | ✅ |
| Flujo de trabajo | ✅ |
| Documentación | ✅ |
| GitHub Actions | ⏳ Pendiente |

---

## 13. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `.github/workflows/` | Workflows de GitHub Actions. |
| `/opt/sportflow/deploy.sh` | Script de despliegue. |
| `docs/02-despliegue.md` | Procedimiento de despliegue. |
| `docs/04-docker.md` | Infraestructura Docker. |

---

## 14. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 12-github.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |