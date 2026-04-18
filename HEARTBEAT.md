# HEARTBEAT.md - Free Clarín

## Ejecutar diariamente a las 10:00 AM (Argentina)

### Paso 1: Scrapear clarin.com

```bash
# Obtener página principal de Clarín
curl -s "https://www.clarin.com/" | grep -oE 'https://www\.clarin\.com/[^"]+' | sort -u > articulos/urls_raw.txt
```

### Paso 2: Verificar y archivar en archive.is

Por cada URL en `articulos/urls_raw.txt`:
- GET `https://archive.is/new/URL` para verificar si existe
- Si existe → guardar URL del archivado
- Si no existe → POST a archive.is para solicitar archivado

### Paso 3: Recrear página tipo Clarín

Generar `site/index.html` con:
- Mismo diseño/estructura visual que Clarín
- Mismos artículos (título, imagen, categoría)
- Enlaces cambiados a URLs de archive.is
- Badge "📦 Archivado" en cada artículo

### Paso 4: Publicar

```bash
cd /home/opc/.openclaw/workspace-freeclarin
git add site/index.html
git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"
git push origin main
```

### Logging

Guardar en `memory/YYYY-MM-DD.md`:
- Artículos encontrados
- Artículos archivados exitosamente
- Artículos que fallaron
- Errores si los hay

## Nota importante

- Respetar delays entre requests a archive.is (rate limit)
- Si archive.is está caído, guardar URLs pendientes y reintentar
