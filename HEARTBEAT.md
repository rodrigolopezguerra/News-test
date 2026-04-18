# HEARTBEAT.md - Free Clarín

## Ejecutar diariamente a las 10:00 AM (Argentina / UTC-3)

---

## Lógica de 3 Capas (prioridad)

### Capa 1: Archives existentes
- **Fuente:** site/index.html + articulos/archivados.json
- **Acción:** Usar directamente sin hacer ningún request a Wayback
- Si el URL ya tiene archive → skip completo

### Capa 2: CDX API check
- **Fuente:** archive.org/cdx/search/cdx?url=...&from=2026
- **Acción:** Verificar si existe snapshot en 2026
- Si existe → usar ese archive, no pedir nuevo
- **Rate limit:** 1 segundo entre requests

### Capa 3: SavePageNow (último recurso)
- **Fuente:** archive.org/save/<url>
- **Acción:** Solo si NO hay archive en Capa 1 ni Capa 2
- **Rate limit:** 5 segundos entre requests (límite ~15 req/min)

---

## Sistema de Reintentos

### URLs Pendientes (awaiting indexing)
Cuando SavePageNow acepta pero el artículo no aparece en CDX aún:
- Guardar en `articulos/pending_urls.json`
- Recheck cada 1 hora (máximo 3 checks)
- Si después de 24h sigue sin indexar → mover a failed

### URLs Fallidas (persistently failed)
- Máximo 3 intentos totales
- Guardar en `articulos/failed_urls.json`
- Después de 3 fallos → no más reintentos automáticos
- Mostrar en sección separada del sitio

### Estructura de tracking
```json
// pending_urls.json
{
  "url": {
    "save_accepted_at": "2026-04-18T09:00:00Z",
    "wayback_url": "https://web.archive.org/save/...",
    "last_checked": "2026-04-18T10:00:00Z",
    "checks": 1,
    "attempts": 1
  }
}

// failed_urls.json
{
  "url": {
    "failed_at": "2026-04-18T09:00:00Z",
    "attempts": 3,
    "reason": "timeout|error|pending_timeout"
  }
}
```

---

## Rate Limits según políticas de Wayback Machine

| API | Límite | Implementado |
|-----|--------|--------------|
| CDX API | ~8 req/seg | 1 req/seg |
| SavePageNow | ~15 req/min | 5 seg entre req |

---

## Flujo completo

```bash
cd /home/opc/.openclaw/workspace-freeclarin

# 1. Archivo: 3 capas + reintentos
python3 archive_robust.py

# 2. Generar sitio
python3 generate_site.py

# (git push es automático al final de archive_robust.py)
```

---

## Logging

Guardar en memory/YYYY-MM-DD.md:
- URLs encontradas, archivadas, pendientes, fallidas
- De cuál capa vino cada archive
- Errores si los hay

---

## Notas

- archive.is = BLOQUEADO en Oracle Cloud
- archive.org = FUNCIONA (CDX + SavePageNow)
- Si HTTP 429 → esperar más, no reintentar inmediatamente
