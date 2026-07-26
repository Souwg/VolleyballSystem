# Base de datos

> **Nivel:** Infraestructura
>
> **Audiencia:** Desarrolladores / Administradores del servidor

---

## 1. Objetivo

La base de datos de SportFlow es el componente encargado de almacenar toda la información del sistema de forma persistente.

Actualmente se utiliza PostgreSQL como motor de base de datos, ofreciendo un entorno robusto, seguro y preparado para el crecimiento de la aplicación.

Toda la información relacionada con clubes, usuarios, categorías, equipos, jugadores, entrenamientos, partidos, pagos y demás módulos se almacena en PostgreSQL.

---

## 2. Descripción general

SportFlow utiliza PostgreSQL ejecutándose dentro de un contenedor Docker independiente.

El acceso a la base de datos se realiza únicamente desde la aplicación Flask mediante SQLAlchemy.

No existen conexiones públicas hacia PostgreSQL.

Toda comunicación ocurre dentro de la red privada creada por Docker Compose.

---

## 3. Arquitectura

```
Usuario
      │
      ▼
Flask API
      │
      ▼
SQLAlchemy
      │
      ▼
PostgreSQL
      │
      ▼
Almacenamiento persistente
```

Toda la comunicación con la base de datos se realiza utilizando SQLAlchemy como ORM.

---

## 4. Motor de base de datos

Actualmente SportFlow utiliza:

```
PostgreSQL 16 Alpine
```

Características principales:

- Base de datos relacional.
- Soporte para transacciones.
- Alta estabilidad.
- Excelente rendimiento.
- Compatibilidad con SQLAlchemy.
- Compatible con Alembic para migraciones.

---

## 5. Conexión desde la aplicación

La aplicación Flask obtiene la conexión mediante la variable de entorno:

```text
DATABASE_URL
```

Esta variable se encuentra en:

```text
/opt/sportflow/docker/.env
```

La cadena de conexión nunca debe almacenarse dentro del código fuente.

---

## 6. SQLAlchemy

SQLAlchemy es el ORM utilizado por SportFlow.

Permite:

- Definir modelos mediante clases Python.
- Crear relaciones entre entidades.
- Ejecutar consultas.
- Administrar transacciones.
- Mantener independencia respecto al motor de base de datos.

Todos los modelos del sistema se encuentran definidos en el backend de la aplicación.

---

## 7. Alembic y migraciones

SportFlow utiliza Alembic para administrar los cambios del esquema de la base de datos.

Las migraciones permiten:

- Crear nuevas tablas.
- Agregar columnas.
- Modificar restricciones.
- Mantener sincronizados todos los entornos.

Las migraciones se ejecutan automáticamente durante cada despliegue mediante:

```text
/opt/sportflow/deploy.sh
```

No es necesario ejecutarlas manualmente durante un despliegue normal.

---

## 8. Backups

Antes de cada despliegue el sistema genera automáticamente una copia de seguridad de PostgreSQL.

Los respaldos se almacenan en:

```text
/opt/sportflow/backups/postgres
```

Esto permite recuperar la información en caso de cualquier inconveniente durante una actualización.

---

## 9. Buenas prácticas

Se recomienda:

- Nunca modificar directamente la base de datos en producción sin una razón justificada.
- Utilizar siempre migraciones para cambios estructurales.
- Mantener respaldos antes de cualquier actualización importante.
- Evitar almacenar información sensible en texto plano.
- Revisar las migraciones antes de desplegarlas.

---

## 10. Troubleshooting

### Error de conexión

Verificar:

- Estado del contenedor `sportflow-database`.
- Variable `DATABASE_URL`.
- Estado de Docker Compose.

---

### Error durante migraciones

Comprobar:

- Logs de la aplicación.
- Estado de Alembic.
- Existencia de archivos de migración pendientes.

---

### Base de datos no disponible

Verificar:

- Estado del contenedor PostgreSQL.
- Espacio disponible en el servidor.
- Estado del volumen de datos.

---

## 11. Checklist

Antes de finalizar un despliegue verificar:

- PostgreSQL iniciado correctamente.
- Aplicación conectada a la base de datos.
- Migraciones ejecutadas.
- Backup generado.
- Estado saludable del contenedor.

---

## 12. Estado actual

| Componente | Estado |
|------------|--------|
| PostgreSQL | ✅ |
| Docker | ✅ |
| SQLAlchemy | ✅ |
| Alembic | ✅ |
| Backups automáticos | ✅ |
| Migraciones automáticas | ✅ |

---

## 13. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `src/models.py` | Modelos principales de la aplicación. |
| `migrations/` | Archivos de migración de Alembic. |
| `/opt/sportflow/docker/.env` | Variables de entorno de la base de datos. |
| `/opt/sportflow/deploy.sh` | Ejecuta automáticamente las migraciones. |

---

## 14. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 06-base-de-datos.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |