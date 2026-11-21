#!/usr/bin/env python3
"""Locate stale custom domain declarations and redirects on public Pages repos."""
import base64
import json
import os
from urllib import error, parse, request
from concurrent.futures import ThreadPoolExecutor, as_completed

OWNER="KrAzad0"
TOKEN=os.getenv("GITHUB_TOKEN","")
HEADERS={"User-Agent":"KrAzad0-pages-custom-domain-audit",
         "Accept":"application/vnd.github+json"}
if TOKEN: HEADERS["Authorization"]="Bearer "+TOKEN

def api(url):
    try:
        with request.urlopen(request.Request(url,headers=HEADERS), timeout=18) as r:
            return r.status,json.load(r)
    except error.HTTPError as exc:
        return exc.code,{}
    except Exception as exc:
        return 0,{"error":str(exc)}

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

no_redirect=request.build_opener(NoRedirect())

def head(url):
    try:
        req=request.Request(url,method="HEAD",headers={"User-Agent":HEADERS["User-Agent"]})
        with no_redirect.open(req,timeout=18) as r:
            return r.status,r.getheader("Location"),str(r.geturl())
    except error.HTTPError as exc:
        return exc.code,exc.headers.get("Location"),str(exc.geturl())
    except Exception as exc:
        return 0,None,str(exc)

def audit(repo):
    name=repo["name"]
    rname=parse.quote(name)
    base=f"https://api.github.com/repos/{OWNER}/{rname}"
    page_status,pages=api(base+"/pages")
    cnames={}
    for ref in sorted(set([repo.get("default_branch","main"),"gh-pages"])):
        for path in ["CNAME","docs/CNAME"]:
            status,file=api(base+f"/contents/{path}?ref="+parse.quote(ref))
            if status==200 and isinstance(file,dict):
                try:
                    content=base64.b64decode(file.get("content","")).decode("utf-8").strip()
                except Exception:
                    content="(unreadable)"
                cnames[f"{ref}:{path}"]=content
    site="https://krazad0.github.io/" if name.lower()=="krazad0.github.io" else f"https://krazad0.github.io/{name}/"
    http,location,final=head(site)
    result={"repo":name,"site":site,"http":http,"redirect_location":location,
            "pages_cname":pages.get("cname") if page_status==200 else None,
            "pages_api_status":page_status,
            "cnames":cnames}
    return result

def main():
    status,repos=api(f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner")
    if status!=200: raise RuntimeError(f"GitHub repo enumeration: HTTP {status}")
    repos=[r for r in repos if r.get("has_pages") and r.get("owner",{}).get("login","").lower()==OWNER.lower()]
    print(f"Found {len(repos)} public repositories with Pages enabled",flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(audit,repo) for repo in repos]
        for f in as_completed(futures):
            r=f.result()
            print(json.dumps(r,ensure_ascii=False),flush=True)
    print("Completed custom-domain scan.")

if __name__=="__main__":main()
