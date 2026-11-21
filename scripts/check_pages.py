#!/usr/bin/env python3
"""Audit public GitHub Pages sites and project pages for KrAzad0.

Scans all PUBLIC repositories with GitHub Pages enabled, discovers standalone
index.html pages in the main portfolio repository, and checks key quantum
mechanics chapter links. Reports HTTP responses and final redirect hosts.
No private repository contents or tokens are printed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OWNER = "KrAzad0"
BASE = "https://krazad0.github.io"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"User-Agent": "KrAzad0-GitHub-Pages-Healthcheck/1.0",
           "Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN

def github_api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def public_repos():
    repos = []
    for p in range(1, 6):
        batch = github_api(f"/users/{OWNER}/repos?per_page=100&page={p}&type=owner")
        repos += [r for r in batch if r.get("owner", {}).get("login", "").lower() == OWNER.lower()]
        if len(batch) < 100:
            break
    return repos

def page_paths():
    result = ["/", "/research-workspace/", "/QM-CH1-SOLUTION/"]
    result += [f"/QM-CH1-SOLUTION/chapter{i}/" for i in range(2, 6)]
    result += ["/QM-CH1-SOLUTION/chapter5/index.html",
               "/QM-CH1-SOLUTION/chapter5/chapter-5-solutions.pdf"]
    try:
        tree = github_api(f"/repos/{OWNER}/{OWNER}.github.io/git/trees/main?recursive=1")
        for obj in tree.get("tree", []):
            path = obj.get("path", "")
            if (path.endswith("/index.html") and path.count("/") <= 3
                    and not any(seg in ("node_modules", "vendor", "_site", ".github")
                                for seg in path.split("/"))):
                result.append("/" + path[:-len("index.html")])
    except Exception as exc:
        print("WARN portfolio directory enumeration:", exc)
    return result

def check(url):
    # HEAD avoids downloading PDFs. Retry short-lived DNS/network failures.
    req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]}, method="HEAD")
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=22) as response:
                return response.status, response.geturl(), ""
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                return e.code, e.geturl(), str(e.reason)
            last = (e.code, e.geturl(), str(e.reason))
        except Exception as e:
            last = (0, url, str(e))
        if attempt < 3:
            time.sleep(1 + attempt)
    return last

def main():
    repos = public_repos()
    pages = [r for r in repos if r.get("has_pages")]
    print(f"Public repositories: {len(repos)}; repositories with Pages: {len(pages)}")
    paths = page_paths()
    for r in pages:
        if r["name"].lower() != f"{OWNER}.github.io".lower():
            paths.append("/" + urllib.parse.quote(r["name"]) + "/")
    paths = sorted(set(paths))
    print(f"Checking {len(paths)} unique public page URLs:")
    failures = []
    for path in paths:
        url = BASE + path
        status, final, err = check(url)
        host = urllib.parse.urlparse(final).hostname
        ok = status == 200 and host == "krazad0.github.io"
        label = "PASS" if ok else "FAIL"
        print(f"{label} {status:3d} {url} => {final}" +
              (f" ({err})" if err else ""), flush=True)
        if not ok:
            failures.append((url, status, final))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as handle:
            handle.write(f"## GitHub Pages health check\n\n")
            handle.write(f"Checked **{len(paths)}** URLs from **{len(pages)}** Pages-enabled public repositories.\n\n")
            handle.write(f"Result: **{len(paths)-len(failures)} passed**, **{len(failures)} failed**.\n\n")
            if failures:
                handle.write("| Failing URL | HTTP | Destination |\n|---|---:|---|\n")
                for url, status, final in failures:
                    handle.write(f"| {url} | {status} | {final} |\n")
    if failures:
        print(f"FAIL: {len(failures)} project URLs need attention.")
        return 1
    print("PASS: all surveyed project pages serve on krazad0.github.io without domain redirection.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
