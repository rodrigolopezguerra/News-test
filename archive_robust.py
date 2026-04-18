#!/usr/bin/env python3
import urllib.request, urllib.parse, json, time, sys, os, re
from datetime import datetime, timedelta

WORKSPACE = "/home/opc/.openclaw/workspace-freeclarin"
TIMEOUT_CDX = 10
TIMEOUT_SAVE = 30
RATE_LIMIT_CDX = 1.0
RATE_LIMIT_SAVE = 5.0
MAX_ATTEMPTS = 3
PENDING_CHECK_INTERVAL = 3600  # 1 hour between pending checks

def get_archived_from_cdx(url):
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        "?url=" + urllib.parse.quote(url)
        + "&output=json&limit=1&filter=statuscode=200"
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
                    return j["url"], j.get("timestamp", "")[:8], "saved"
            final_url = resp.geturl()
            if "web.archive.org" in final_url:
                return final_url, "pending", "pending"
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower():
            return None, None, "rate_limited"
        if "timeout" in err_str.lower():
            return None, None, "timeout"
        return None, None, "error"
    return None, None, "unknown"

def load_json(filepath, default):
    try:
        with open(filepath) as f:
            return json.load(f)
    except:
        return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_existing_archives():
    archived = {}
    # From site/index.html
    try:
        with open(WORKSPACE + "/site/index.html") as f:
            site_content = f.read()
        pattern = r'href="(https://web\.archive\.org/web/(\d+)/([^"]+))"'
        for m in re.findall(pattern, site_content):
            orig = m[2]
            if orig not in archived:
                archived[orig] = {"wayback_url": m[0], "timestamp": m[1], "source": "site"}
    except:
        pass
    # From archivados.json
    try:
        data = load_json(WORKSPACE + "/articulos/archivados.json", {"results": []})
        for r in data.get("results", []):
            if r.get("wayback_url"):
                orig = r.get("original_url", "")
                if orig and orig not in archived:
                    archived[orig] = {"wayback_url": r["wayback_url"], "timestamp": r.get("timestamp", ""), "source": "json"}
    except:
        pass
    return archived

def load_pending():
    return load_json(WORKSPACE + "/articulos/pending_urls.json", {})

def load_failed():
    return load_json(WORKSPACE + "/articulos/failed_urls.json", {})

def check_pending_urls(pending, results):
    """Check pending URLs that may have been indexed since last check."""
    now = datetime.utcnow()
    updated_pending = {}
    checked = 0
    
    for url, info in pending.items():
        last_check = datetime.fromisoformat(info.get("last_checked", "2020-01-01T00:00:00"))
        checks = info.get("checks", 0)
        
        # Only check if enough time has passed (1 hour)
        if (now - last_check).total_seconds() < PENDING_CHECK_INTERVAL:
            updated_pending[url] = info
            continue
        
        print("  [PENDING CHECK] " + url.split("/")[-1][:40] + " (check #" + str(checks + 1) + ")", flush=True)
        arch_url, ts = get_archived_from_cdx(url)
        checked += 1
        
        if arch_url:
            results[url] = {"wayback_url": arch_url, "timestamp": ts, "source": "cdx"}
            print("    -> FOUND: " + str(ts))
        else:
            checks += 1
            if checks >= 3:
                # Move to failed
                failed = load_failed()
                failed[url] = {"failed_at": now.isoformat(), "attempts": info.get("attempts", 1), "reason": "pending_timeout"}
                save_json(WORKSPACE + "/articulos/failed_urls.json", failed)
                print("    -> TIMEOUT, moved to failed")
            else:
                info["checks"] = checks
                info["last_checked"] = now.isoformat()
                updated_pending[url] = info
                print("    -> Still pending")
        
        time.sleep(RATE_LIMIT_CDX)
    
    return updated_pending, checked

def git_push():
    import subprocess
    try:
        print("")
        print("=== Git Push ===")
        subprocess.run(["git", "add", "site/index.html", "index.html", "articulos/", "memory/"],
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
    now = datetime.utcnow()
    
    # Load URLs to process
    with open(WORKSPACE + "/articulos/urls.txt") as f:
        all_urls = [line.strip() for line in f if line.strip() and "clarin.com" in line]
    print("URLs to process: " + str(len(all_urls)))
    
    # Load tracking files
    pending = load_pending()
    failed = load_failed()
    archived = load_existing_archives()
    
    # Results accumulator
    results = dict(archived)
    
    # Check pending URLs first (may have been indexed since yesterday)
    if pending:
        print("")
        print("  [PENDING] Checking " + str(len(pending)) + " pending URLs...")
        pending, pending_checked = check_pending_urls(pending, results)
        save_json(WORKSPACE + "/articulos/pending_urls.json", pending)
    
    # Exclude failed URLs (permanently failed after 3 attempts)
    failed_urls = set(failed.keys())
    to_process = [u for u in all_urls if u not in results and u not in failed_urls]
    print("  After layers: " + str(len(results)) + " archived, " + str(len(to_process)) + " to process, " + str(len(failed_urls)) + " permanently failed")
    
    # Capa 2: CDX API check for URLs not archived
    cdx_hits = 0
    cdx_checked = 0
    if to_process:
        print("")
        print("  [Capa 2] CDX API check for " + str(len(to_process)) + " URLs...")
        for i, url in enumerate(to_process, 1):
            slug = url.split("/")[-1][:40]
            print("  [" + str(i) + "/" + str(len(to_process)) + "] CDX: " + slug, flush=True)
            arch_url, ts = get_archived_from_cdx(url)
            cdx_checked += 1
            if arch_url:
                results[url] = {"wayback_url": arch_url, "timestamp": ts, "source": "cdx"}
                cdx_hits += 1
                print("    -> FOUND: " + str(ts))
            else:
                print("    -> No archive 2026")
            time.sleep(RATE_LIMIT_CDX)
        print("  [Capa 2] CDX hits: " + str(cdx_hits))
    
    # Capa 3: SavePageNow for URLs still not archived
    to_archive = [u for u in all_urls if u not in results and u not in failed_urls]
    print("")
    print("  [Capa 3] Need new archive: " + str(len(to_archive)))
    
    new_success = 0
    new_pending = 0
    new_failed = 0
    
    for i, url in enumerate(to_archive, 1):
        slug = url.split("/")[-1][:40]
        print("  [" + str(i) + "/" + str(len(to_archive)) + "] SAVE: " + slug, flush=True)
        
        arch_url, ts, status = save_to_wayback(url)
        
        if status == "saved" and arch_url:
            # Verify it's in CDX (might be immediate or pending)
            time.sleep(2)  # Brief wait for CDX to update
            verify_url, verify_ts = get_archived_from_cdx(url)
            if verify_url:
                results[url] = {"wayback_url": verify_url, "timestamp": verify_ts, "source": "new"}
                new_success += 1
                print("    -> SUCCESS (verified)")
            else:
                # Save accepted but not indexed yet
                pending[url] = {
                    "save_accepted_at": now.isoformat(),
                    "wayback_url": arch_url,
                    "last_checked": now.isoformat(),
                    "checks": 0,
                    "attempts": 1
                }
                new_pending += 1
                print("    -> PENDING (not indexed yet)")
        elif status == "pending" and arch_url:
            pending[url] = {
                "save_accepted_at": now.isoformat(),
                "wayback_url": arch_url,
                "last_checked": now.isoformat(),
                "checks": 0,
                "attempts": 1
            }
            new_pending += 1
            print("    -> PENDING")
        else:
            # Error occurred
            if url in failed:
                failed[url]["attempts"] += 1
                failed[url]["last_attempt"] = now.isoformat()
                failed[url]["last_error"] = status
            else:
                failed[url] = {
                    "failed_at": now.isoformat(),
                    "attempts": 1,
                    "reason": status
                }
            
            if failed[url]["attempts"] >= MAX_ATTEMPTS:
                print("    -> FAILED (max attempts reached)")
            else:
                print("    -> FAILED (" + status + "), will retry")
            new_failed += 1
        
        time.sleep(RATE_LIMIT_SAVE)
    
    # Save updated tracking files
    save_json(WORKSPACE + "/articulos/pending_urls.json", pending)
    save_json(WORKSPACE + "/articulos/failed_urls.json", failed)
    
    # Summary
    print("")
    print("=== RESULTS ===")
    print("Total URLs: " + str(len(all_urls)))
    print("Archives: " + str(len(results)) + " (Capa 1+2+3)")
    print("  - From site: " + str(sum(1 for v in results.values() if v.get("source") == "site")))
    print("  - From CDX: " + str(sum(1 for v in results.values() if v.get("source") == "cdx")))
    print("  - New: " + str(new_success))
    print("Pending (awaiting indexing): " + str(len(pending)))
    print("Failed: " + str(new_failed) + " new, " + str(len(failed)) + " total")
    
    # Save archivados.json
    output = {
        "timestamp": now.isoformat(),
        "total": len(all_urls),
        "archived": len(results),
        "pending": len(pending),
        "failed": len(failed),
        "results": [{"original_url": url, **data} for url, data in results.items()]
    }
    save_json(WORKSPACE + "/articulos/archivados.json", output)
    
    # Git push
    git_push()
    
    return output

if __name__ == "__main__":
    main()
