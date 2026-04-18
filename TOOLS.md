# TOOLS.md - Free Clarín Agent

## Workspace
- **Path:** /home/opc/.openclaw/workspace-freeclarin
- **Repo:** rodrigolopezguerra/News-test
- **GitHub Pages:** https://rodrigolopezguerra.github.io/News-test/

## Scripts
- `archive_robust.py` - Main archive script (3-layer + retry logic)
- `generate_site.py` - Generate site/index.html from archives
- Both located in workspace root

## Data Files
- `articulos/urls.txt` - URLs de artículos a procesar
- `articulos/archivados.json` - URLs ya archivadas con éxito
- `articulos/pending_urls.json` - URLs pendientes de indexación
- `articulos/failed_urls.json` - URLs fallidas (3+ intentos)

## APIs Used
- **Wayback CDX API:** Check existing archives (1 req/sec limit)
- **Wayback SavePageNow:** Create new archives (5 sec between requests)
- archive.is = BLOCKED (Oracle Cloud DNS failure)

## Rate Limits
| API | Limit | Implemented |
|-----|-------|------------|
| CDX API | ~8 req/sec | 1 sec delay |
| SavePageNow | ~15 req/min | 5 sec delay |

## Retry Logic
- **Pending:** Recheck cada 1h, máximo 3 veces (24h total)
- **Failed:** Máximo 3 intentos, después = permanently failed
- **Same day:** URLs pendientes se re-checkean en próximas ejecuciones del día

## Cron Schedule
- Daily at 06:00 ART (09:00 UTC)
- Job ID: 247e038f-eeae-4b3d-a745-774ae65b6ae0
