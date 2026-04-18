#!/usr/bin/env python3
"""
Generate site/index.html from urls.txt + archivados.json

Uses 3-layer logic:
  1. Archives from archivados.json (if exists)
  2. Archives from site/index.html (already generated)
  3. Direct clarin.com links as fallback (badge: No archivado)
"""
import json
import re
import time
from datetime import datetime

WORKSPACE = '/home/opc/.openclaw/workspace-freeclarin'

def extract_title_from_url(url):
    """Extract readable title from URL slug."""
    match = re.search(r'clarin\.com/[^/]+/(.+)_[A-Za-z0-9]+\.html', url)
    if match:
        slug = match.group(1)
        title = slug.replace('-', ' ').replace('_', ' ')
        return title.title()
    return url.split('/')[-1].replace('.html', '').replace('-', ' ').replace('_', ' ')

def load_archives():
    """Load existing archives from archivados.json."""
    archives = {}
    try:
        with open(WORKSPACE + '/articulos/archivados.json') as f:
            data = json.load(f)
        for r in data.get('results', []):
            orig = r.get('original_url', '')
            wayback = r.get('wayback_url', '')
            ts = r.get('timestamp', '')
            if orig and wayback:
                archives[orig] = {'wayback_url': wayback, 'timestamp': ts}
        print(f"  Loaded {len(archives)} archives from archivados.json")
    except Exception as e:
        print(f"  Warning: could not load archivados.json: {e}")
    return archives

def load_archives_from_site():
    """Load archives already in site/index.html."""
    archives = {}
    try:
        with open(WORKSPACE + '/site/index.html') as f:
            content = f.read()
        for m in re.findall(r'href="(https://web\.archive\.org/web/(\d+)/([^"]+))"', content):
            orig = m[2]
            if orig not in archives:
                archives[orig] = {'wayback_url': m[0], 'timestamp': m[1]}
        print(f"  Loaded {len(archives)} archives from site/index.html")
    except Exception as e:
        print(f"  Warning: could not load from site: {e}")
    return archives

def generate_site():
    print("=== Generate Site ===")
    
    with open(WORKSPACE + '/articulos/urls.txt') as f:
        urls = [line.strip() for line in f if line.strip() and 'clarin.com' in line]
    print(f"Total URLs: {len(urls)}")
    
    archives_v3 = load_archives()
    archives_site = load_archives_from_site()
    all_archives = {**archives_v3, **archives_site}
    print(f"Total unique archives: {len(all_archives)}")
    
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    html = '''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-type" content="text/html; charset=utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>Free Clarín - Archivo Alternativo</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
h1 { color: #e53935; border-bottom: 2px solid #e53935; padding-bottom: 10px; }
.section-title { font-size: 1.3em; margin: 30px 0 15px; color: #333; border-left: 4px solid #e53935; padding-left: 10px; }
.article { background: white; border-radius: 8px; padding: 15px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.article-title { font-size: 1.05em; font-weight: 600; margin-bottom: 8px; line-height: 1.4; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
.badge-archived { background: #4caf50; color: white; }
.badge-noarchive { background: #ff9800; color: white; }
.article-link { display: inline-block; padding: 5px 12px; background: #e53935; color: white; text-decoration: none; border-radius: 4px; font-size: 0.85em; }
.article-link:hover { background: #c62828; }
.article-meta { font-size: 0.75em; color: #999; margin-top: 5px; }
.footer { text-align: center; margin-top: 40px; color: #999; font-size: 0.8em; }
.header-stats { background: #fff3e0; padding: 10px 15px; border-radius: 8px; margin: 15px 0; }
</style>
</head>
<body>
<h1>📰 Free Clarín</h1>
<div style="opacity:0.8">Archivo alternativo de noticias de Clarín.com</div>
<div class="header-stats">
<b>Total artículos: ''' + str(len(urls)) + '''</b> — <b>Archivados: ''' + str(len(all_archives)) + '''</b> — Actualizado: ''' + now + '''
</div>
<h2 class="section-title">✅ Artículos Archivados</h2>
'''
    
    archived_count = 0
    unarchived_count = 0
    
    for url in urls:
        title = extract_title_from_url(url)
        
        if url in all_archives:
            arch = all_archives[url]
            ts = arch['timestamp']
            if len(ts) >= 8:
                date_str = ts[:4] + '-' + ts[4:6] + '-' + ts[6:8]
            else:
                date_str = ts
            html += '<div class="article">\n<div class="article-title">' + title + '</div>\n'
            html += '<a href="' + arch['wayback_url'] + '" target="_blank" class="article-link">📦 Ver Archivo</a>\n'
            html += '<div class="article-meta">Archivado: ' + date_str + '</div>\n</div>\n'
            archived_count += 1
        else:
            html += '<div class="article">\n<div class="article-title">' + title + '</div>\n'
            html += '<a href="' + url + '" target="_blank" class="article-link">🔗 Ver en Clarín</a>\n'
            html += '<span class="badge badge-noarchive">⚠️ No archivado</span>\n'
            html += '<div class="article-meta">Sin archive disponible</div>\n</div>\n'
            unarchived_count += 1
    
    html += '''
<div class="footer">
<p>⚠️ Este archivo es solo para uso personal/educativo. El contenido pertenece a Clarín.</p>
<p>Generado por Free Clarín Bot</p>
</div>
</body>
</html>
'''
    
    with open(WORKSPACE + '/site/index.html', 'w') as f:
        f.write(html)
    
    with open(WORKSPACE + '/index.html', 'w') as f:
        f.write(html)
    
    print(f"\n=== Generated site/index.html ===")
    print(f"Total URLs: {len(urls)}")
    print(f"  - Archivados: {archived_count}")
    print(f"  - Sin archive: {unarchived_count}")
    
    return {'total': len(urls), 'archived': archived_count, 'unarchived': unarchived_count}

if __name__ == '__main__':
    generate_site()
