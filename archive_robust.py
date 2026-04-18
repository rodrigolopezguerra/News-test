#!/usr/bin/env python3
"""Archive articles to Wayback Machine - robust version with proper rate limits.

LÓGICA DE 3 CAPAS:
  Prioridad 1: Usar archive existente en site/index.html y archivados.json
  Prioridad 2: Checkear CDX API por snapshots 2026
  Prioridad 3: Solo si no hay ninguno → pedir SavePageNow

RATE LIMITS (según políticas de Wayback Machine):
  - CDX API: 1 segundo entre requests (ya que soporta ~8 req/seg)
  - SavePageNow: 5 segundos entre requests (límite ~15 req/min)
"""
import urllib.request
import urllib.parse
import json
import time
import sys
import os
import re

WORKSPACE = '/home/opc/.openclaw/workspace-freeclarin'

# Rate limits según Wayback Machine policies
TIMEOUT_CDX = 10        # CDX API timeout
TIMEOUT_SAVE = 30       # SavePageNow timeout
RATE_LIMIT_CDX = 1.0   # CDX API: 1 segundo (soporta ~8 req/seg)
RATE_LIMIT_SAVE = 5.0  # SavePageNow: 5 segundos (límite ~15 req/min)

def get_archived_from_cdx(url):
    """Check CDX API for existing archive in 2026."""
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url={urllib.parse.quote(url)}"
        f"&output=json&limit=1&filter=statuscode:200"
        f"&from=2026&to=2026"
    )
    try:
        req = urllib.request.Request(
            cdx_url,
            headers={'User-Agent': 'Mozilla/5.0 FreeClarinsBot/1.0'}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_CDX) as resp:
            data = json.loads(resp.read().decode())
            if len(data) > 1:
                ts = data[1][1]
                return f"https://web.archive.org/web/{ts}/{url}", ts
    except Exception as e:
        print(f"      CDX error: {e}")
    return None, None

def save_to_wayback(url):
    """Save URL to Wayback Machine via SavePageNow API. RETURNS NONE if fails."""
    save_url = f"https://web.archive.org/save/{url}"
    try:
        req = urllib.request.Request(
            save_url,
            headers={
                'User-Agent': 'Mozilla/5.0 FreeClarinsBot/1.0',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SAVE) as resp:
            content = resp.read().decode()
            if 'url' in content:
                j = json.loads(content)
                if 'url' in j:
                    return j['url'], j.get('timestamp', '')[:8]
            # Si fue redirigido directamente al archive
            final_url = resp.geturl()
            if 'web.archive.org' in final_url:
                ts_match = re.search(r'/web/(\d+)', final_url)
                ts = ts_match.group(1)[:8] if ts_match else ''
                return final_url, ts
    except Exception as e:
        print(f"      Save error: {e}")
    return None, None

def load_existing_archives():
    """CAPA 1: Cargar archives existentes desde site/index.html y archivados.json."""
    archived = {}
    
    # Desde site/index.html
    try:
        with open(f'{WORKSPACE}/site/index.html') as f:
            content = f.read()
        for m in re.findall(r'href="(https://web\.archive\.org/web/(\d+)/([^"]+))"', content):
            orig = m[2]
            if orig not in archived:
                archived[orig] = {'wayback_url': m[0], 'timestamp': m[1], 'source': 'site'}
        print(f"  [Capa 1] {len(archived)} archives cargados desde site/index.html")
    except Exception as e:
        print(f"  [Capa 1] No se pudo parsear site: {e}")
    
    # Desde archivados.json
    try:
        with open(f'{WORKSPACE}/articulos/archivados.json') as f:
            existing = json.load(f)
        for r in existing.get('results', []):
            if r.get('status') == 'success' and r.get('wayback_url'):
                orig = r.get('original_url', '')
                if orig and orig not in archived:
                    archived[orig] = {
                        'wayback_url': r['wayback_url'],
                        'timestamp': r.get('timestamp', ''),
                        'source': 'json'
                    }
        print(f"  [Capa 1] Total tras archivados.json: {len(archived)}")
    except Exception as e:
        print(f"  [Capa 1] No se pudo cargar archivados.json: {e}")
    
    return archived

def main():
    print("=== Free-Clarín Archive Script ===")
    print(f"Workspace: {WORKSPACE}")
    
    # 0. Cargar URLs a procesar
    with open(f'{WORKSPACE}/articulos/urls.txt') as f:
        all_urls = [line.strip() for line in f if line.strip() and 'clarin.com' in line]
    print(f"URLs a procesar: {len(all_urls)}")
    
    # CAPA 1: Usar archives existentes
    archived = load_existing_archives()
    
    # Determinar cuáles necesitan проверка
    to_check = [u for u in all_urls if u not in archived]
    print(f"  [Capa 1] Ya archivados: {len(archived)}, Necesitan check: {len(to_check)}")
    
    # CAPA 2: Checkear CDX para URLs sin archive
    results = dict(archived)
    cdx_hits = 0
    
    print(f"\n  [Capa 2] Verificando CDX API para {len(to_check)} URLs...")
    for i, url in enumerate(to_check, 1):
        print(f"  [{i}/{len(to_check)}] CDX check: {url.split('/')[-1][:40]}", flush=True)
        
        arch_url, ts = get_archived_from_cdx(url)
        if arch_url:
            results[url] = {'wayback_url': arch_url, 'timestamp': ts, 'source': 'cdx'}
            cdx_hits += 1
            print(f"    → FOUND: {ts}")
        else:
            print(f"    → No archive 2026")
        
        time.sleep(RATE_LIMIT_CDX)
    
    print(f"  [Capa 2] CDX hits: {cdx_hits}")
    
    # CAPA 3: Archivar solo los que NO tienen archive
    to_archive = [u for u in all_urls if u not in results]
    print(f"\n  [Capa 3] Necesitan archivado nuevo: {len(to_archive)}")
    
    success = 0
    failed = 0
    
    for i, url in enumerate(to_archive, 1):
        slug = url.split('/')[-1][:40]
        print(f"  [{i}/{len(to_archive)}] SAVE: {slug}", flush=True)
        
        arch_url, ts = save_to_wayback(url)
        if arch_url:
            results[url] = {'wayback_url': arch_url, 'timestamp': ts, 'source': 'new'}
            success += 1
            print(f"    → SUCCESS: {arch_url[:60]}")
        else:
            failed += 1
            print(f"    → FAILED")
        
        # Rate limit para SavePageNow: 5 segundos
        time.sleep(RATE_LIMIT_SAVE)
    
    # Guardar resultados
    print(f"\n=== RESULTADOS ===")
    print(f"Total URLs: {len(all_urls)}")
    print(f"Archives usados (Capa 1+2): {len(results)}")
    print(f"  - Desde site: {sum(1 for v in results.values() if v.get('source') == 'site')}")
    print(f"  - Desde CDX: {sum(1 for v in results.values() if v.get('source') == 'cdx')}")
    print(f"  - Nuevos (Capa 3): {success}")
    print(f"Fallidos: {failed}")
    
    # Guardar JSON para uso del generador del sitio
    output = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total': len(all_urls),
        'archived': len(results),
        'success': success,
        'failed': failed,
        'results': [
            {'original_url': url, **data}
            for url, data in results.items()
        ]
    }
    with open(f'{WORKSPACE}/articulos/archivados.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    return output

if __name__ == '__main__':
    main()
