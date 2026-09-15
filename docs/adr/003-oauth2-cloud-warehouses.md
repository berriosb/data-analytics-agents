# ADR-003 — Soporte OAuth2 / service-principal para cloud warehouses

> **Propósito:** Capturar las decisiones arquitectónicas para agregar
> autenticación OAuth2 a `sql-cloud-warehouse` en los warehouses que
> la soportan de forma nativa, sin reemplazar los mecanismos de
> credenciales estáticas existentes.

- **Status:** Draft (2026-09-15)
- **ADR previo:** [001-portable-day1](./001-portable-day1.md),
  [002-end-to-end-delivery](./002-end-to-end-delivery.md)
- **Owner:** CodeHak (Bastian)

## Contexto

`sql-cloud-warehouse` (v0.4.0 → v0.9.0) soporta 4 warehouses (Snowflake,
BigQuery, Redshift, Databricks) con autenticación estática en env vars:

| Warehouse | Credenciales actuales (v0.9.0) |
|---|---|
| Snowflake | `SNOWFLAKE_PASSWORD` (user/password) |
| BigQuery | `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON path) |
| Redshift | `REDSHIFT_PASSWORD` (user/password + host) |
| Databricks | `DATABRICKS_TOKEN` (personal access token) |

Esto funciona para desarrollo local y para muchos setups corporativos,
pero hay 3 brechas reales que aparecen en producción:

1. **Seguridad corporativa** — empresas con SOC2 / ISO27001 prohíben
   passwords largos en `.env`. Quieren OAuth contra el IdP corporativo
   (Okta, Azure AD, Google Workspace).
2. **Rotación automática** — los personal access tokens (PATs) de
   Databricks expiran (default 90 días) y requieren intervencion
   manual. OAuth access tokens expiran más rápido pero se refrescan
   solos via refresh tokens.
3. **Sin secrets en disco** — algunos shops (bancos, fintech) requieren
   que ninguna credencial toque el filesystem del data analyst. OAuth
   sin refresh token en disco cumple esto.

Estas 3 motivaciones justifican agregar OAuth2 a los warehouses que
la soportan de forma nativa y razonable, **sin romper** el flujo de
credenciales estáticas existente (que sigue siendo válido para dev).

## Decisiones arquitectónicas

### 1. Scope por warehouse — qué se agrega, qué se difiere

| Warehouse | Estado v0.9.0 | Propuesta v1.0 | Por qué |
|---|---|---|---|
| Snowflake | user/password | **+ OAuth (external IdP)** | Soporte nativo en `snowflake-connector-python` via `authenticator='oauth'` + access token. Patrón estándar corporativo. |
| Databricks | PAT | **+ Service principal OAuth** | Soporte nativo via `databricks-sdk` + OAuth client credentials flow. Permite rotation automática. |
| BigQuery | service account JSON | Sin cambios | Ya cumple el rol de OAuth (service account = OAuth credential). No hay gap. |
| Redshift | user/password | Sin cambios v1 | Redshift usa IAM roles via `redshift-connector` + STS AssumeRole, no OAuth2 nativo. ADR aparte si se necesita. |

### 2. Stack de cada flujo nuevo

| Flujo | Librería base | Por qué |
|---|---|---|
| Snowflake OAuth | `snowflake-connector-python` (ya peerDep) | Soporta `authenticator='oauth'` + `token=<access_token>`. Sin libs nuevas. |
| Databricks OAuth | `databricks-sdk` (peerDep nueva, opcional) | SDK oficial de Databricks. Maneja el client credentials flow (POST a `/oidc/v1/token` con client_id+client_secret → access token). |

### 3. Credenciales via env vars (mismas reglas que v0.9.0)

- **Sin secrets hardcodeados** — todo via env vars / vault.
- **Snowflake OAuth**:
  - `SNOWFLAKE_OAUTH_TOKEN` — access token ya emitido por el IdP
    (el caller maneja el flow completo con su IdP).
  - Alternativa: `SNOWFLAKE_OAUTH_CLIENT_ID` + `SNOWFLAKE_OAUTH_CLIENT_SECRET`
    + `SNOWFLAKE_OAUTH_REFRESH_TOKEN` + `SNOWFLAKE_OAUTH_AUTH_URL` para
    el flow completo (mas complejo, v1.x).
- **Databricks service principal**:
  - `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` + `DATABRICKS_OIDC_ENDPOINT`
    — el SDK maneja el client credentials flow automáticamente.

### 4. Dispatch por `auth_method` (no auto-detect)

El usuario declara el método via env var o argumento explícito:

```python
# Snowflake: detecta OAuth si SNOWFLAKE_OAUTH_TOKEN esta seteado,
# si no usa el flow de password existente.
warehouse_type, auth_method = detect_auth_method("snowflake", env=os.environ)
```

Esto evita "magia" — el usuario siempre sabe qué flow se está usando.
Default behavior: si no se setea nada nuevo, se usa el flow de v0.9.0
(backward compatible).

### 5. Guardrails (mismas reglas del toolkit)

- **Sin tokens en logs** — los snippets usan `__repr__` que redacta
  access tokens / refresh tokens / client secrets.
- **Audit log extendido** — cuando se use OAuth, el log registra
  `auth_method: oauth` ademas del SQL ejecutado.
- **Errores accionables** — si falta una env var de OAuth,
  `MissingCredentialsError` lista exactamente qué var falta y un
  link al SKILL.md sección "Credenciales".

### 6. Multi-CLI compatibility — sin cambios

Los snippets nuevos son markdown + Python, viven en
`skills/sql-cloud-warehouse/recetas/connect.py` (extensión del
existente). Sin cambios a `bin/install.js`, `AGENTS.md`, ni al
frontmatter.

### 7. Distribución — sigue siendo una sola publicación npm

- `databricks-sdk` se agrega como peerDep opcional en `package.json`.
- Sin paquetes separados.
- `requirements-dev.txt` no la incluye (peerDep opcional, el usuario
  decide).

## Trade-offs considerados

### ¿Por qué no OAuth unificado via una sola lib?

OAuth flows divergen entre proveedores (Snowflake espera access token
externo, Databricks hace client credentials flow, BigQuery usa service
account JSON). Una capa de abstracción agregaría complejidad sin
beneficio — el caller ya sabe qué warehouse está usando.

### ¿Por qué no forzar OAuth siempre?

Rompe backward compatibility (v0.9.0 users con passwords en .env
dejarían de funcionar). OAuth es opt-in via env vars nuevas; el flujo
existente sigue funcionando.

### ¿Por qué no incluir BigQuery OAuth installed-app flow?

BigQuery ya tiene service account JSON (peerDep opcional, cubre el 90%
del caso corporativo). El installed-app flow (para uso personal sin
service account) es de nicho — si hay demanda, ADR aparte.

### ¿Por qué no incluir Redshift IAM role assumption v1?

Es mecanismo diferente a OAuth2 (es AWS STS, no OAuth). amerita su
propio ADR con su propio set de trade-offs (rol chaining, MFA delete,
etc.).

## Riesgos

- **`SNOWFLAKE_OAUTH_TOKEN` expira rapido** — el caller tiene que
  refrescarlo. La skill NO maneja refresh tokens en v1 (asume que
  el caller usa un IdP que emite tokens de larga duracion o que
  rota tokens manualmente). Documentado en el SKILL.md.
- **Databricks SDK pesa ~10 MB** — se declara como peerDep opcional.
  Si el usuario solo usa Snowflake OAuth, no la necesita.
- **Cambios en OAuth flows** — los proveedores cambian endpoints y
  scopes. Tests deben ser contra mocks, no contra servicios reales.

## Relación con docs existentes

- `skills/sql-cloud-warehouse/SKILL.md` — agregar seccion "OAuth"
  con los env vars por warehouse + ejemplo end-to-end.
- `docs/prd/sql-cloud-warehouse.md` — flip status a Accepted (ya está)
  + agregar nueva sección "OAuth flows".
- `package.json` — agregar `databricks-sdk` como peerDep opcional.
- `CHANGELOG.md` — entrada v1.0.0 mencionando OAuth como opt-in.

## Estimación

- ADR (este doc): 30 min (hecho).
- Implementación `_connect_snowflake_oauth` + dispatch: 1.5 h.
- Implementación `_connect_databricks_service_principal` + tests: 2 h.
- Tests con mocks (sin red): 1 h.
- SKILL.md update + .env.example: 30 min.

**Total: ~5 h de código + tests.**
