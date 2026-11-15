#!/usr/bin/env python3
"""
sigma_cli.py - push / export Sigma workbook YAML specs (Workbooks-as-Code) from the command line.

Security model (each user uses THEIR OWN Sigma API client):
  * Client ID and Client Secret are typed at a hidden prompt (getpass) and kept only in memory.
    They are never printed, logged, written to disk or put on the command line / in shell history.
  * Optional non-interactive mode (CI only): pass --use-env and provide SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET
    from a secret store. Without --use-env, environment variables are ignored (no silent use of leftovers).
  * Credentials and tokens are only sent over HTTPS to *.sigmacomputing.com (the base URL is validated).
  * The connectionId is substituted in memory; the YAML file on disk is not modified.

Standard library only (Python 3.8+).

Examples:
  python sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com connections
  python sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com workbooks
  python sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com push --yaml my_page.yaml
  python sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com export --workbook-id <uuid> --out wb.yaml
"""
import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_merge  # noqa: E402  (same folder)
import token_cache  # noqa: E402  (same folder)

KNOWN_HOSTS = [
    "https://api.us.azure.sigmacomputing.com",
    "https://aws-api.sigmacomputing.com",
    "https://api.sigmacomputing.com",
    "https://aws-api.eu.sigmacomputing.com",
]
PLACEHOLDER = "REPLACE_WITH_SIGMA_CONNECTION_ID"
# Sigma's API has no "save as draft": every PUT .../spec creates a new PUBLISHED version (see version-history).
PUBLISH_WARNING = ("  WARNING: this PUBLISHES the workbook immediately (Sigma's API cannot save to the edit draft).\n"
                   "  Anyone with access sees the new version. If you have a Draft open in the Sigma editor, it is now\n"
                   "  outdated: discard it after publishing (publishing that draft would bring the old version back).")
UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def validate_base_url(url):
    p = urllib.parse.urlparse(url.strip().rstrip("/"))
    if p.scheme != "https" or not (p.hostname or "").endswith(".sigmacomputing.com") or p.path not in ("", "/"):
        die("the base URL must be https://<host>.sigmacomputing.com (credentials are only sent to Sigma).")
    return f"https://{p.hostname}"


class Sigma:
    def __init__(self, base_url):
        self.base = base_url
        self.host = urllib.parse.urlparse(base_url).hostname
        self.token = None
        self.from_cache = False
        self._login_args = {}

    def _send(self, method, path, data, headers, auth):
        h = {"Accept": "application/json"}
        if auth:
            h["Authorization"] = f"Bearer {self.token}"
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except urllib.error.URLError as e:
            die(f"could not reach {self.base}: {e.reason}")

    def _request(self, method, path, data=None, headers=None, auth=True):
        status, raw = self._send(method, path, data, headers, auth)
        if status == 401 and auth and self.from_cache:
            # reused token was rejected (revoked / rotated secret): forget it and sign in again, once
            token_cache.clear(self.host)
            print("Saved session token was rejected; please sign in again.")
            self.login(cache=False, **self._login_args)
            status, raw = self._send(method, path, data, headers, auth)
        return status, raw

    def login(self, use_env=False, gui=False, cache=True):
        self._login_args = {"use_env": use_env, "gui": gui}
        if cache and not use_env:
            tok = token_cache.load(self.host)
            if tok:
                self.token, self.from_cache = tok, True
                print(f"Reusing this Windows session's Sigma token for {self.host} "
                      f"(expires in {token_cache.remaining(self.host) // 60} min; 'logout' forgets it).")
                return
        self.from_cache = False
        if gui:      # native window: the user never needs a terminal; values stay in memory only
            import sigma_gui
            cid, sec = sigma_gui.login(self.base)
            if not cid or not sec:
                die("sign-in cancelled or empty.", 3)
        elif use_env:  # explicit opt-in only (CI with a secret store); leftover variables are never picked up silently
            cid = os.environ.get("SIGMA_CLIENT_ID")
            sec = os.environ.get("SIGMA_CLIENT_SECRET")
            if not (cid and sec):
                die("--use-env given but SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET are not both set.")
            print("Using SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET from the environment (--use-env).")
        else:
            if not sys.stdin.isatty():
                die("no terminal for the hidden prompt; run it in an interactive terminal (or use --use-env in CI).")
            cid = getpass.getpass("Sigma Client ID (hidden): ").strip()
            sec = getpass.getpass("Sigma Client Secret (hidden): ").strip()
        if not cid or not sec:
            die("Client ID and Client Secret are required.")
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}).encode()
        del cid, sec
        status, raw = self._request("POST", "/v2/auth/token", data=body,
                                    headers={"Content-Type": "application/x-www-form-urlencoded"}, auth=False)
        del body
        if status != 200:
            # never echo the request; the response body of a failed login carries no secret
            die(f"authentication failed on {self.base} (HTTP {status}). Check your own Client ID/Secret "
                f"and the base URL for your Sigma organization.")
        resp = json.loads(raw)
        self.token = resp.get("access_token")
        if not self.token:
            die("authentication returned no access token.")
        print(f"Authenticated on {self.base}")
        if cache and not use_env and token_cache.save(self.host, self.token, resp.get("expires_in")):
            print("Session token kept for up to 1 hour in Windows Credential Manager (this logon only). "
                  "Run 'logout' to forget it now.")

    def get_json(self, path):
        status, raw = self._request("GET", path)
        if status != 200:
            die(f"GET {path.split('?')[0]} -> HTTP {status}: {raw[:500].decode('utf-8', 'replace')}")
        return json.loads(raw)

    def list_all(self, path):
        items, page = [], None
        while True:
            sep = "&" if "?" in path else "?"
            url = f"{path}{sep}limit=500" + (f"&page={urllib.parse.quote(str(page))}" if page else "")
            j = self.get_json(url)
            items += j.get("entries", [])
            page = j.get("nextPage")
            if not page:
                return items


def print_table(rows, cols):
    widths = [max(len(c), *(len(str(r.get(c, ""))) for r in rows)) if rows else len(c) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(cols, widths)))


def ask(prompt, validator=None):
    while True:
        v = input(prompt).strip()
        if not validator or validator(v):
            return v
        print("  invalid value, try again.")


def cmd_connections(s, a):
    print_table(s.list_all("/v2/connections"), ["connectionId", "name", "type"])


def cmd_workbooks(s, a):
    print_table(s.list_all("/v2/workbooks"), ["workbookId", "name", "path"])


def cmd_export(s, a):
    status, raw = s._request("GET", f"/v2/workbooks/{a.workbook_id}/spec", headers={"Accept": "application/yaml"})
    if status != 200:
        die(f"export failed (HTTP {status}): {raw[:500].decode('utf-8', 'replace')}")
    with open(a.out, "wb") as f:
        f.write(raw)
    print(f"Saved {len(raw)} bytes to {a.out}")


def get_document(s, wb):
    j = s.get_json(f"/v2/workbooks/{wb}/spec?format=json")
    return j.get("name", "?"), j.get("document") or {}


def cmd_pages(s, a):
    name, doc = get_document(s, a.workbook_id)
    print(f"Workbook: {name}")
    rows = [{"pageId": p.get("id"), "name": p.get("name"), "visibility": p.get("visibility", "")} for p in doc.get("pages", [])]
    print_table(rows, ["pageId", "name", "visibility"])


def cmd_push(s, a):
    if not os.path.isfile(a.yaml):
        die(f"file not found: {a.yaml}")
    text = open(a.yaml, encoding="utf-8").read()
    gui = a.gui
    if gui:
        import sigma_gui
    conn = a.connection_id
    if PLACEHOLDER in text and not conn:
        rows = s.list_all("/v2/connections")
        if gui:
            conn = sigma_gui.choose("Choose the Sigma connection used by the report's SQL", rows,
                                    ["name", "type", "connectionId"], "connectionId",
                                    "It must reach the Snowflake semantic views (e.g. your company's Snowflake connection).")
            if not conn:
                die("cancelled by the user (no connection chosen).", 3)
        else:
            print_table(rows, ["connectionId", "name", "type"])
            conn = ask(f"connectionId to replace {PLACEHOLDER}: ", lambda v: bool(UUID_RE.match(v)))
    print(f"connectionId: {conn or '(not needed)'}")
    wb = a.workbook_id
    if not wb:
        rows = s.list_all("/v2/workbooks")
        if gui:
            wb = sigma_gui.choose("Choose the TARGET workbook (the report becomes a page/tab in it)", rows,
                                  ["name", "path", "workbookId"], "workbookId",
                                  "Other pages are kept. A page with the same name as the report is replaced.")
            if not wb:
                die("cancelled by the user (no workbook chosen).", 3)
        else:
            print()
            print_table(rows, ["workbookId", "name", "path"])
            wb = ask("\nworkbookId of the target workbook: ", lambda v: bool(UUID_RE.match(v)))
    wb_name, wb_doc = get_document(s, wb)
    print(f"\nWorkbook '{wb_name}' ({wb}) - current pages (tabs):")
    print_table([{"pageId": p.get("id"), "name": p.get("name"), "visibility": p.get("visibility", "")}
                 for p in wb_doc.get("pages", [])], ["pageId", "name", "visibility"])

    attempt = 0
    while True:
        attempt += 1
        try:                                                     # re-read every attempt: fix the file between tries
            report = spec_merge.load_report_file(a.yaml, conn)
        except (spec_merge.MergeError, ValueError) as e:
            die(str(e))
        name, current = get_document(s, wb)
        if a.replace_workbook:
            merged, summary = report, {"replaced_pages": ["<whole workbook>"], "added_pages": [],
                                       "kept_pages": [], "removed_elements": "all", "kept_elements": 0,
                                       "report_elements": len(report["elements"])}
        else:
            try:
                merged, summary = spec_merge.merge(current, report)
            except spec_merge.MergeError as e:
                die(str(e))
        if attempt == 1:
            print(f"\nWorkbook '{name}' ({wb})")
            print(PUBLISH_WARNING)
            print(f"  pages kept   : {', '.join(summary['kept_pages']) or '-'}")
            print(f"  pages added  : {', '.join(summary['added_pages']) or '-'}")
            print(f"  pages REPLACED: {', '.join(summary['replaced_pages']) or '-'}")
            backup = f"backup_{wb[:8]}_{time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup, "w", encoding="utf-8") as f:       # restore with: push --replace-workbook --yaml <backup>
                json.dump({"document": current}, f, ensure_ascii=False, indent=1)
            print(f"  backup of the current workbook: {os.path.abspath(backup)}")
            if a.dry_run:
                print("DRY RUN: nothing was sent to Sigma.")
                return
            if gui and not a.yes:
                pages_now = "\n".join(f"   - {p.get('name')}" for p in current.get("pages", [])) or "   -"
                txt = (f"Workbook: {name}\n{wb}\n\nCurrent pages:\n{pages_now}\n\n"
                       f"Pages KEPT    : {', '.join(summary['kept_pages']) or '-'}\n"
                       f"Pages ADDED   : {', '.join(summary['added_pages']) or '-'}\n"
                       f"Pages REPLACED: {', '.join(summary['replaced_pages']) or '-'}\n\n"
                       f"Backup saved: {os.path.abspath(backup)}")
                if not sigma_gui.confirm("Publish the report in this workbook?", txt,
                                         warning=PUBLISH_WARNING.strip(), ok_label="Publish"):
                    die("cancelled by the user.", 3)
            elif not a.yes:
                ok = ask("Publish? [y/N]: ").lower()
                if ok not in ("y", "yes"):
                    die("cancelled by the user.", 0)
        body = json.dumps({"document": merged}, ensure_ascii=False).encode("utf-8")
        status, raw = s._request("PUT", f"/v2/workbooks/{wb}/spec", data=body,
                                 headers={"Content-Type": "application/json"})
        msg = raw.decode("utf-8", "replace")
        if a.log:
            with open(a.log, "w", encoding="utf-8") as f:     # Sigma's response only - never credentials
                f.write(("OK" if status == 200 else f"ERROR HTTP {status}") + "\n" + ("" if status == 200 else msg))
        if status == 200:
            print(f"OK: '{name}' PUBLISHED (added: {', '.join(summary['added_pages']) or '-'}; "
                  f"replaced: {', '.join(summary['replaced_pages']) or '-'}). Reload the workbook in Sigma; if the editor "
                  f"shows an older Draft, discard it (publishing that draft would bring the old version back).")
            return
        print(f"Sigma rejected the spec (HTTP {status}); nothing was changed:")
        try:
            j = json.loads(msg)
            for e in j.get("errors") or [{"summary": j.get("message", msg)}]:
                print("  -", e.get("summary"))
            print("  requestId:", j.get("requestId"))
        except ValueError:
            print(msg[:2000])
        if a.no_retry or gui:          # GUI mode: Claude reads this output, fixes the report and runs it again
            sys.exit(2)
        if input("Fix the YAML and press Enter to resend (q to quit): ").strip().lower() == "q":
            sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="Sigma Workbooks-as-Code CLI (credentials via hidden prompt).")
    ap.add_argument("--base-url", default=os.environ.get("SIGMA_BASE_URL"),
                    help="Sigma API host of YOUR org, e.g. " + ", ".join(KNOWN_HOSTS) + " (or env SIGMA_BASE_URL)")
    ap.add_argument("--gui", action="store_true",
                    help="no terminal needed: native windows for sign-in, workbook/connection choice and confirmation "
                         "(used when Claude runs the CLI for the user)")
    ap.add_argument("--use-env", action="store_true",
                    help="CI only: read SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET from the environment instead of prompting")
    ap.add_argument("--no-cache", action="store_true",
                    help="always sign in; do not reuse or keep the 1-hour session token")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("logout", help="forget the reused session token for this host now (no sign-in needed)")
    sub.add_parser("connections", help="list connections (connectionId, name, type)")
    sub.add_parser("workbooks", help="list workbooks (workbookId, name, path)")
    e = sub.add_parser("export", help="download a workbook spec as YAML")
    e.add_argument("--workbook-id", required=True)
    e.add_argument("--out", required=True)
    g = sub.add_parser("pages", help="list the pages (tabs) of a workbook")
    g.add_argument("--workbook-id", required=True)
    p = sub.add_parser("push", help="add/replace the report's page(s) in an existing workbook, keeping the other pages")
    p.add_argument("--yaml", required=True, help="report spec (.yaml needs PyYAML, or .json); "
                                                 "REPLACE_WITH_SIGMA_CONNECTION_ID is substituted in memory")
    p.add_argument("--workbook-id", help="target workbook (listed and asked if omitted)")
    p.add_argument("--connection-id", help="Sigma connection used by the SQL sources (listed and asked if omitted)")
    p.add_argument("--replace-workbook", action="store_true",
                   help="replace the WHOLE workbook with the file (default: merge pages by name)")
    p.add_argument("--yes", action="store_true", help="do not ask before applying")
    p.add_argument("--dry-run", action="store_true", help="show what would change (and save the backup) without pushing")
    p.add_argument("--no-retry", action="store_true", help="exit on the first error (CI)")
    p.add_argument("--log", help="optional file for Sigma's last response (no credentials are written)")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):               # workbook names may contain non-ASCII characters
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    if not a.base_url:
        print("Sigma API host for your organization:")
        for i, h in enumerate(KNOWN_HOSTS, 1):
            print(f"  {i}. {h}")
        c = ask("Choose 1-4 or paste the URL: ")
        a.base_url = KNOWN_HOSTS[int(c) - 1] if c.isdigit() and 1 <= int(c) <= len(KNOWN_HOSTS) else c
    s = Sigma(validate_base_url(a.base_url))
    if a.cmd == "logout":
        token_cache.clear(s.host)
        print(f"Session token for {s.host} forgotten (nothing else was stored).")
        return
    if a.no_cache:
        token_cache.clear(s.host)
    s.login(use_env=a.use_env, gui=a.gui, cache=not a.no_cache)
    {"connections": cmd_connections, "workbooks": cmd_workbooks, "export": cmd_export, "pages": cmd_pages,
     "push": cmd_push}[a.cmd](s, a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("interrupted.", 130)
