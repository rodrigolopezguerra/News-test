# HEARTBEAT.md - Free Clarín

## Ejecutar diariamente a las 10:00 AM (Argentina)

### Flujo completo

```python
import subprocess
import json
from datetime import datetime

# 1. Scrapear clarin.com
print("=== Free Clarín: Iniciando scrap ===")
result = subprocess.run(
    ['curl', '-s', '--connect-timeout', '15', 'https://www.clarin.com/'],
    capture_output=True, text=True
)
html = result.stdout

# Extraer URLs de artículos
import re
urls = re.findall(r'"url":"(https://www\.clarin\.com/[^"]+)"', html)
urls = list(set(urls))  # Deduplicar
print(f"Artículos encontrados: {len(urls)}")

# 2. Verificar y archivar en archive.org con waybackpy
archived = []
pending = []

for url in urls:
    # Verificar si ya está archivado
    check = subprocess.run(
        ['curl', '-s', f'https://archive.org/wayback/available?url={url}'],
        capture_output=True, text=True
    )
    data = json.loads(check.stdout)
    
    if data.get('archived_snapshots', {}).get('closest'):
        archived_url = data['archived_snapshots']['closest']['url']
        archived.append({'original': url, 'archived': archived_url})
    else:
        # Archivar con waybackpy
        save_result = subprocess.run(
            ['waybackpy', '-s', '-u', url],
            capture_output=True, text=True
        )
        if 'Archive URL:' in save_result.stdout:
            archived_url = save_result.stdout.split('Archive URL:')[1].strip()
            archived.append({'original': url, 'archived': archived_url})
        else:
            pending.append(url)
        import time
        time.sleep(2)  # Rate limit

# 3. Recrear página tipo Clarín con enlaces archivados
generate_site(archived)

# 4. Git push
subprocess.run(['git', 'add', 'site/index.html'], cwd='/home/opc/.openclaw/workspace-freeclarin')
subprocess.run(['git', 'commit', '-m', f'Update: {datetime.now().strftime("%Y-%m-%d %H:%M")}'], cwd='/home/opc/.openclaw/workspace-freeclarin')
subprocess.run(['git', 'push', 'origin', 'main'], cwd='/home/opc/.openclaw/workspace-freeclarin')

# 5. Reportar
print(f"""
=== Free Clarín: Completado ===
Artículos archivados: {len(archived)}
Pendientes: {len(pending)}
Sitio: https://rodrigolopezguerra.github.io/News-test/
""")
```

### Logging

Guardar en `memory/YYYY-MM-DD.md`:
- Artículos encontrados, archivados, fallidos
- Errores si los hay

## IMPORTANTE

- **NO usar archive.is** — bloqueado en Oracle Cloud
- **USAR waybackpy** — archiva en archive.org
- Respetar delays de 2 segundos entre archivos para no saturar la API
