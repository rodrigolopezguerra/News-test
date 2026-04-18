# HEARTBEAT.md - Free Clarín

## Ejecutar diariamente a las 10:00 AM (Argentina / UTC-3)

---

## Lógica de 3 Capas (prioridad)

### Capa 1: Archives existentes
- **Fuente:** site/index.html + articulos/archivados.json
- **Acción:** Usar directamente sin hacer ningún request a Wayback
- Si el URL ya tiene archive en el sitio → skip completo

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

## Rate Limits según políticas de Wayback Machine

| API | Límite | Implementado |
|-----|--------|--------------|
| CDX API | ~8 req/seg | 1 req/seg ✅ |
| SavePageNow | ~15 req/min | 5 seg entre req ✅ |

**IMPORTANTE:** 
- 1.5 segundos para SavePageNow es DEMASIADO RÁPIDO y causa HTTP 429
- Mínimo 4 segundos, usar 5 segundos para seguridad

---

## Flujo completo

1. Scrape: obtener URLs de clarin.com
2. Archivo: python3 archive_robust.py (3 capas)
3. Generar sitio: site/index.html
4. Git push a origin main

---

## Logging

Guardar en memory/YYYY-MM-DD.md:
- URLs encontradas, archivadas, fallidas
- De cuál capa vino cada archive
- Errores si los hay

---

## Notas

- archive.is = BLOQUEADO en Oracle Cloud
- archive.org = FUNCIONA (CDX + SavePageNow)
- Si HTTP 429 → esperar más, no reintentar inmediatamente
