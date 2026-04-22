#!/usr/bin/env python3
"""
Free Clarín - Wayback Monitor (pasivo via CDX)
Estrategia: no intentar guardar, solo consultar CDX para detectar cuando aparece archivado.
Después de 3 días sin archivar → marcar como OLD.
"""
import json, time, sys, os, urllib.parse, urllib.request
from datetime import datetime, timezone

ARTICULOS_DIR = "/home/opc/.openclaw/workspace-freeclarin/articulos"
PENDING_FILE = os.path.join(ARTICULOS_DIR, "pending_archive.json")
ARCHIVADOS_FILE = os.path.join(ARTICULOS_DIR, "archivados.json")
CHECKPOINT_FILE = os.path.join(ARTICULOS_DIR, "checkpoint.json")
LOG_DIR = "/home/opc/.openclaw/workspace-freeclarin/memory"
MEMORY_FILE = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md")

OLD_THRESHOLD_DAYS = 3
CDX_URL = "https://web.archive.org/cdx/search/cdx"
RATE_LIMIT = 1.0

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(MEMORY_FILE, "a") as f:
        f.write(line + "\n")

def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def check_cdx(url, retries=2):
    """Consulta CDX para ver si la URL está archivada. Retorna timestamp o None."""
    cdx_api_url = f"{CDX_URL}?url={url}&output=json&limit=1&filter=statuscode:200&from=2026"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(cdx_api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode()
                if data.strip().startswith("["):
                    entries = json.loads(data)
                    # entries[0] = header row, entries[1+] = data rows
                    if len(entries) > 1:
                        timestamp = entries[1][1]  # [url, timestamp, original, ...]
                        return timestamp
                    return None
        except Exception as e:
            log(f"  CDX error: {e}")
            time.sleep(2)
    return None

def main():
    log("=== Wayback Monitor (CDX pasivo) ===")
    
    pending = load_json(PENDING_FILE, [])
    if not isinstance(pending, list):
        pending = []
    
    archivados = load_json(ARCHIVADOS_FILE, {"results": []})
    archived_urls = {a["original_url"] for a in archivados["results"]}
    checkpoint = load_json(CHECKPOINT_FILE, {})
    first_seen = checkpoint.get("first_seen", {})
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Filtrar ya archivados
    pending = [u for u in pending if u not in archived_urls]
    log(f"Pendientes a verificar: {len(pending)}")
    
    archived_this_run = []
    marked_old = []
    still_pending = []
    old_items = checkpoint.get("old_items", [])
    old_urls = {o["url"] for o in old_items}
    
    for i, url in enumerate(pending):
        print(f"\r  [{i+1}/{len(pending)}] {url[:70]}", end="", flush=True)
        
        # Edades
        first = first_seen.get(url, now_iso)
        try:
            first_dt = datetime.fromisoformat(first.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - first_dt).total_seconds() / 86400
        except:
            age_days = 0
        
        timestamp = check_cdx(url)
        time.sleep(RATE_LIMIT)
        
        if timestamp:
            wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"
            archivados["results"].append({
                "original_url": url,
                "wayback_url": wayback_url,
                "timestamp": timestamp
            })
            archived_this_run.append(url)
            log(f"  ✓ ARCHIVADO: {url[:70]} ({timestamp})")
        elif age_days >= OLD_THRESHOLD_DAYS:
            old_items.append({"url": url, "tag": "OLD", "first_seen": first})
            marked_old.append(url)
            log(f"  ✗ OLD: {url[:70]}")
        else:
            first_seen[url] = first
            still_pending.append(url)
    
    print()
    
    save_json(ARCHIVADOS_FILE, archivados)
    save_json(PENDING_FILE, still_pending)
    checkpoint["first_seen"] = {u: first_seen[u] for u in first_seen if u in still_pending}
    checkpoint["old_items"] = old_items
    checkpoint["last_cycle"] = {
        "date": now_iso,
        "total": len(pending),
        "archived": len(archived_this_run),
        "marked_old": len(marked_old),
        "still_pending": len(still_pending)
    }
    save_json(CHECKPOINT_FILE, checkpoint)
    
    log(f"=== Resumen ===")
    log(f"  Archivados: {len(archived_this_run)} | OLD: {len(marked_old)} | Restan: {len(still_pending)}")
    log(f"  Total archivados: {len(archivados['results'])}")

if __name__ == "__main__":
    main()
