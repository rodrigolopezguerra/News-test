#!/usr/bin/env python3
import urllib.request, urllib.parse, json, time, sys, os, re
WORKSPACE = "/home/opc/.openclaw/workspace-freeclarin"
TIMEOUT_CDX = 10
TIMEOUT_SAVE = 30
RATE_LIMIT_CDX = 1.0
RATE_LIMIT_SAVE = 5.0

def get_archived_from_cdx(url):
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        "?url=" + urllib.parse.quote(url)
        + "&output=json&limit=1&filter=statuscode:200"
        + "&from=2026&to=2026"
    )
    try:
        req = urllib.request.Request(cdx_url, headers={"User-Agent": "Mozilla/5.0 FreeClarinsBot/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_CDX) as resp:
            data = json.loads(resp.read().decode())
            if len(data) > 1:
                ts = data[1][1]
                return "https://web.archive.org/web/" + ts + "/" + url, ts
    except:
        pass
    return None, None

def save_to_wayback(url):
    save_url = "https://web.archive.org/save/" + url
    try:
        req = urllib.request.Request(
            save_url,
            headers={"User-Agent": "Mozilla/5.0 FreeClarinsBot/1.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SAVE) as resp:
            content = resp.read().decode()
            if "url" in content:
                j = json.loads(content)
                if "url" in j:
                    return j["url"], j.get("timestamp", "")[:8]
            final_url = resp.geturl()
            if "web.archive.org" in final_url:
                ts_match = re.search(r"/web/(\d+)", final_url)
                ts = ts_match.group(1)[:8] if ts_match else ""
                return final_url, ts
    except:
        pass
    return None, None

def load_existing_archives():
    archived = {}
    try:
        with open(WORKSPACE + "/site/index.html") as f:
            site_content = f.read()
        pattern = r'href="(https://web\.archive\.org/web/(\d+)/([^"]+))"'
        for m in re.findall(pattern, site_content):
            orig = m[2]
            if orig not in archived:
                archived[orig] = {"wayback_url": m[0], "timestamp": m[1], "source": "site"}
        print("  [Capa 1] " + str(len(archived)) + " archives from site/index.html")
    except Exception as e:
        print("  [Capa 1] Could not parse site: " + str(e))
    try:
        with open(WORKSPACE + "/articulos/archivados.json") as f:
            existing = json.load(f)
        for r in existing.get("results", []):
            if r.get("wayback_url"):
                orig = r.get("original_url", "")
                if orig and orig not in archived:
                    archived[orig] = {"wayback_url": r["wayback_url"], "timestamp": r.get("timestamp", ""), "source": "json"}
        print("  [Capa 1] Total: " + str(len(archived)))
    except Exception as e:
        print("  [Capa 1] Could not load archivados.json: " + str(e))
    return archived

def git_push():
    import subprocess
    try:
        print("")
        print("=== Git Push ===")
        subprocess.run(["git", "add", "site/index.html", "index.html", "articulos/archivados.json", "articulos/urls.txt"],
                      cwd=WORKSPACE, capture_output=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        result = subprocess.run(["git", "commit", "-m", "Update: " + timestamp + " - Free Clarindo daily run"],
                              cwd=WORKSPACE, capture_output=True, text=True)
        if result.returncode == 0:
            print("  Commit: " + timestamp)
            push = subprocess.run(["git", "push", "origin", "main"], cwd=WORKSPACE, capture_output=True, text=True)
            if push.returncode == 0:
                print("  Push: OK")
                return True
            else:
                print("  Push failed")
                return False
        else:
            print("  Commit skipped (no changes)")
            return False
    except Exception as e:
        print("  Git error: " + str(e))
        return False

def main():
    print("=== Free-Clarin Archive Script ===")
    with open(WORKSPACE + "/articulos/urls.txt") as f:
        all_urls = [line.strip() for line in f if line.strip() and "clarin.com" in line]
    print("URLs to process: " + str(len(all_urls)))
    
    archived = load_existing_archives()
    to_check = [u for u in all_urls if u not in archived]
    print("  Already archived: " + str(len(archived)) + ", Need check: " + str(len(to_check)))
    
    results = dict(archived)
    cdx_hits = 0
    
    print("")
    print("  [Capa 2] Checking CDX API for " + str(len(to_check)) + " URLs...")
    for i, url in enumerate(to_check, 1):
        slug = url.split("/")[-1][:40]
        print("  [" + str(i) + "/" + str(len(to_check)) + "] CDX check: " + slug, flush=True)
        arch_url, ts = get_archived_from_cdx(url)
        if arch_url:
            results[url] = {"wayback_url": arch_url, "timestamp": ts, "source": "cdx"}
            cdx_hits += 1
            print("    -> FOUND: " + str(ts))
        else:
            print("    -> No archive 2026")
        time.sleep(RATE_LIMIT_CDX)
    
    print("  [Capa 2] CDX hits: " + str(cdx_hits))
    
    to_archive = [u for u in all_urls if u not in results]
    print("")
    print("  [Capa 3] Need new archive: " + str(len(to_archive)))
    
    success = 0
    failed = 0
    
    for i, url in enumerate(to_archive, 1):
        slug = url.split("/")[-1][:40]
        print("  [" + str(i) + "/" + str(len(to_archive)) + "] SAVE: " + slug, flush=True)
        arch_url, ts = save_to_wayback(url)
        if arch_url:
            results[url] = {"wayback_url": arch_url, "timestamp": ts, "source": "new"}
            success += 1
            print("    -> SUCCESS")
        else:
            failed += 1
            print("    -> FAILED")
        time.sleep(RATE_LIMIT_SAVE)
    
    print("")
    print("=== RESULTS ===")
    print("Total URLs: " + str(len(all_urls)))
    print("Archives used (Capa 1+2): " + str(len(results)))
    site_count = sum(1 for v in results.values() if v.get("source") == "site")
    cdx_count = sum(1 for v in results.values() if v.get("source") == "cdx")
    print("  - From site: " + str(site_count))
    print("  - From CDX: " + str(cdx_count))
    print("  - New (Capa 3): " + str(success))
    print("Failed: " + str(failed))
    
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(all_urls),
        "archived": len(results),
        "success": success,
        "failed": failed,
        "results": [{"original_url": url, **data} for url, data in results.items()]
    }
    with open(WORKSPACE + "/articulos/archivados.json", "w") as f:
        json.dump(output, f, indent=2)
    
    git_push()
    return output

if __name__ == "__main__":
    main()
