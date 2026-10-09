#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
export_coze_project.py
======================
Pull your Coze project's structure down to local files, so you can diff and
grep it the way you would a Dify .yml.

WHY THIS EXISTS
---------------
Coze DOES have a Dify-style export: a workflow can be exported as a Zip
containing MANIFEST.yml + a workflow/ folder of DSL .yaml files. But that
button is documented as 仅付费套餐 (paid plans only), and it only covers
workflows -- not the agent.

This script uses the documented OpenAPI instead, which is available on the
free plan, and which returns strictly more for debugging purposes:

  GET /v1/workflows
        Query the workflow list of a workspace. Permission: listWorkflow
        Docs: docs.coze.cn/developer_guides/get_workflow_list

  GET /v1/workflows/{workflow_id}?include_input_output=true
        Workflow basic info. include_input_output=true additionally returns
        the INPUT AND OUTPUT PARAMETER STRUCTURE -- i.e. the contract your
        code nodes must match. Permission: getMetaData
        Docs: docs.coze.cn/developer_guides_get_workflow_info

  GET /v1/workflows/{workflow_id}/versions
        Every historical version: version number, description, operator,
        publish time. Docs: developer_guides changelog, added 2025-07-24

  GET /v1/bots/{bot_id}            ?is_published=true|false
        The AGENT config -- published version, or current draft.
        Permission: getMetadata   Docs: developer_guides/get_metadata_draft_published

  GET /v1/bots/{bot_id}/versions
        Agent version list. Permission: Bot.listVersion
        Docs: docs.coze.cn/developer_guides_list_bot_versions

Everything lands in --out as JSON plus a SUMMARY.md index.

WHERE TO FIND THE TWO IDs YOU NEED
----------------------------------
workspace_id : open the workspace; it is the number after /w/ in the URL,
               e.g. https://code.coze.cn/w/75814654762959***/projects
bot_id       : open the agent; it is the number after /bot/ in the URL,
               e.g. https://www.coze.cn/space/341****/bot/73428668*****

USAGE
-----
    # 1) prove the plumbing works, no token needed:
    python export_coze_project.py --mock

    # 2) real run (reads .env next to this script's ../..):
    python export_coze_project.py --workspace 75814654762959******

PAT PERMISSIONS THIS NEEDS (missing any one gives error 4101)
------------------------------------------------------------
    listWorkflow        -> /v1/workflows
    getMetaData        -> /v1/workflows/{id}
    getMetadata        -> /v1/bots/{id}      (note: no capital D)
    Bot.listVersion    -> /v1/bots/{id}/versions
Workflow-version listing needs no extra scope beyond the workspace PAT.

NOTE ON HONESTY: this was written against the documented request/response
schemas and verified end-to-end only in --mock mode (no live token was
available at the time of writing). Every call is wrapped so that a failure
prints the HTTP status and the raw response body instead of a traceback.
If a field name has drifted, the raw dump will show you the real one.
"""

import argparse
import json
import os
import re
import sys

try:
    import requests
except ImportError:
    print("This script needs the 'requests' package:\n"
          "    pip install requests")
    sys.exit(1)


# --------------------------------------------------------------------------
# tiny .env loader, so python-dotenv is optional
# --------------------------------------------------------------------------
def load_env(start_dir):
    """Walk up from start_dir looking for a .env and parse KEY=VALUE lines."""
    d = os.path.abspath(start_dir)
    for _ in range(5):
        candidate = os.path.join(d, ".env")
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    # do not clobber a real environment variable
                    os.environ.setdefault(k, v)
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------
class CozeClient(object):
    def __init__(self, base, token, mock=False):
        self.base = base.rstrip("/")
        self.token = token
        self.mock = mock
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path + (("?" + json.dumps(params)) if params else ""))
        if self.mock:
            canned = MOCK_RESPONSES.get(path)
            if canned is None:
                return 200, {"code": 4999,
                             "msg": "mock: no canned payload for " + path,
                             "data": None}
            return 200, canned

        url = self.base + path
        headers = {
            "Authorization": "Bearer " + (self.token or ""),
            "Content-Type": "application/json",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
        except Exception as exc:
            return 0, {"_transport_error": str(exc), "_url": url}

        try:
            body = r.json()
        except Exception:
            body = {"_raw_text": r.text[:2000]}
        return r.status_code, body

    def fetch(self, path, params=None):
        """GET, then unwrap Coze's {code,msg,data} envelope.

        Returns (data, error_string, status). error_string is "" on success.
        """
        status, body = self.get(path, params)

        if not isinstance(body, dict):
            return None, "non-JSON response (HTTP %s): %r" % (status, body), status
        if "_transport_error" in body:
            return None, "transport error: %s (url=%s)" % (
                body["_transport_error"], body.get("_url", "?")), status
        if "_raw_text" in body:
            return None, "could not parse JSON (HTTP %s): %s" % (
                status, body["_raw_text"][:300]), status

        code = body.get("code")
        if code not in (0, None):
            hint = ""
            if str(code) == "4101":
                hint = " -> the PAT is missing a scope for this endpoint"
            return None, "code=%s msg=%s (HTTP %s)%s" % (
                code, body.get("msg"), status, hint), status

        return body.get("data"), "", status


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(text, fallback="unnamed"):
    text = SAFE.sub("_", str(text or "").strip())
    text = text.strip("_")
    return text[:80] or fallback


def rel(path, base):
    """Relative path with forward slashes, so markdown tables stay readable."""
    return os.path.relpath(path, base).replace(os.sep, "/")


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
    return os.path.getsize(path)


# --------------------------------------------------------------------------
# the export steps
# --------------------------------------------------------------------------
def collect(client, workspace_id, bot_id, out_dir):
    report = []          # (label, status, note, filename)
    saved = {}

    # ---- 1. workflow list -------------------------------------------------
    data, err, _ = client.fetch("/v1/workflows", {
        "workspace_id": workspace_id, "page_num": 1, "page_size": 30,
    })
    workflows = []
    if err:
        report.append(("Workflow list", "FAILED", err, ""))
    else:
        if isinstance(data, dict):
            workflows = data.get("workflow_list") or data.get("items") or []
            # some builds nest under a differently-named key; take first list
            if not workflows:
                for v in data.values():
                    if isinstance(v, list) and v:
                        workflows = v
                        break
        elif isinstance(data, list):
            workflows = data
        fn = os.path.join(out_dir, "workflows.list.json")
        saved["list"] = fn
        write_json(fn, data)
        report.append(("Workflow list", "ok", "%d workflow(s)" % len(workflows),
                       rel(fn, out_dir)))

    # ---- 2. per-workflow info + versions ----------------------------------
    wf_index = []
    for wf in workflows:
        if not isinstance(wf, dict):
            continue
        wid = (wf.get("workflow_id") or wf.get("id")
               or wf.get("workflowId") or "")
        wname = wf.get("name") or wf.get("workflow_name") or wid or "workflow"
        if not wid:
            continue
        wdir = os.path.join(out_dir, "workflows", safe_name(wname, str(wid)))

        # 2a. info + I/O schema  (the part that tells you what your code node owes)
        info, err, _ = client.fetch("/v1/workflows/" + str(wid),
                                    {"include_input_output": "true"})
        if err:
            report.append(("  %s info" % wname, "FAILED", err, ""))
            info_rel = ""
        else:
            fn = os.path.join(wdir, "info.json")
            write_json(fn, info)
            info_rel = rel(fn, out_dir)
            report.append(("  %s info" % wname, "ok",
                           "includes I/O schema", info_rel))

        # 2b. version history
        vers, verr, _ = client.fetch("/v1/workflows/%s/versions" % wid,
                                     {"page_num": 1, "page_size": 30})
        if verr:
            report.append(("  %s versions" % wname, "note", verr, ""))
        else:
            fn = os.path.join(wdir, "versions.json")
            write_json(fn, vers)
            report.append(("  %s versions" % wname, "ok", "",
                           rel(fn, out_dir)))

        wf_index.append({"id": wid, "name": wname,
                         "dir": rel(wdir, out_dir),
                         "info": info_rel})

    # ---- 3. agent config (draft + published) ------------------------------
    if bot_id:
        for label, published in (("published", "true"), ("draft", "false")):
            cfg, err, _ = client.fetch("/v1/bots/" + str(bot_id),
                                       {"is_published": published})
            if err:
                report.append(("Agent config (%s)" % label, "FAILED", err, ""))
            else:
                fn = os.path.join(out_dir, "agent", "config.%s.json" % label)
                write_json(fn, cfg)
                report.append(("Agent config (%s)" % label, "ok", "",
                               rel(fn, out_dir)))

        vers, err, _ = client.fetch("/v1/bots/%s/versions" % bot_id,
                                    {"page_num": 1, "page_size": 30})
        if err:
            report.append(("Agent versions", "note", err, ""))
        else:
            fn = os.path.join(out_dir, "agent", "versions.json")
            write_json(fn, vers)
            report.append(("Agent versions", "ok", "", rel(fn, out_dir)))
    else:
        report.append(("Agent config", "skipped", "no --bot-id given", ""))

    return report, wf_index


# --------------------------------------------------------------------------
# SUMMARY.md  -- something you can actually read
# --------------------------------------------------------------------------
def write_summary(out_dir, report, wf_index, ctx):
    lines = []
    lines.append("# Coze project export\n")
    lines.append("Generated by `scripts/export_coze_project.py`"
                 + (" in **MOCK** mode — these numbers are sample data."
                    if ctx["mock"] else "") + "\n")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append("| API base | `%s` |" % ctx["base"])
    lines.append("| workspace_id | `%s` |" % (ctx["workspace_id"] or "—"))
    lines.append("| bot_id | `%s` |" % (ctx["bot_id"] or "—"))
    lines.append("")

    lines.append("## Files\n")
    lines.append("| Step | Status | Note | File |")
    lines.append("|---|---|---|---|")
    for label, status, note, fn in report:
        lines.append("| %s | %s | %s | `%s` |" % (label, status, note, fn or "—"))
    lines.append("")

    if wf_index:
        lines.append("## Workflows found\n")
        lines.append("| Name | workflow_id | Files |")
        lines.append("|---|---|---|")
        for w in wf_index:
            lines.append("| `%s` | `%s` | `%s/` |" % (w["name"], w["id"], w["dir"]))
        lines.append("")

    lines.append("## What to do with this\n")
    lines.append("- `workflows/<name>/info.json` is the important one: with "
                 "`include_input_output=true` it carries the parameter structure, "
                 "so you can check your code node's declared **输出** against what "
                 "the workflow actually promises.")
    lines.append("- `agent/config.draft.json` vs `agent/config.published.json` "
                 "is the diff that explains why a fix \"did nothing\" — the agent "
                 "keeps using the last *published* version.")
    lines.append("- For a live failure, the sharper tool is `debug_url` "
                 "(see Appendix D.3) — it shows per-node input/output for a real run.")
    lines.append("")

    fn = os.path.join(out_dir, "SUMMARY.md")
    with open(fn, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return fn


# --------------------------------------------------------------------------
# canned payloads so the plumbing is testable without a token
# --------------------------------------------------------------------------
MOCK_RESPONSES = {
    "/v1/workflows": {
        "code": 0, "msg": "",
        "data": {
            "workflow_list": [
                {"workflow_id": "738958910358870001", "name": "generate_questions",
                 "description": "Generate assessment questions on a topic"},
                {"workflow_id": "738958910358870002", "name": "score_answer",
                 "description": "Score a trainee answer"},
                {"workflow_id": "738958910358870003", "name": "analyze_gaps",
                 "description": "Analyse weak areas"},
            ]
        },
    },
    "/v1/workflows/738958910358870001": {
        "code": 0, "msg": "",
        "data": {
            "workflow_id": "738958910358870001",
            "workflow_name": "generate_questions",
            "description": "Generate assessment questions on a topic",
            "input_params": [
                {"name": "topic", "type": "string", "required": True},
                {"name": "difficulty", "type": "string", "required": False},
                {"name": "count", "type": "integer", "required": False},
            ],
            "output_params": [
                {"name": "questions", "type": "array"},
            ],
        },
    },
    "/v1/workflows/738958910358870001/versions": {
        "code": 0, "msg": "",
        "data": {"items": [
            {"version": "1.0.0", "description": "first publish",
             "creator": "you", "publish_time": 1759700000},
        ]},
    },
    "/v1/bots/7342866800000001": {
        "code": 0, "msg": "",
        "data": {
            "bot_id": "7342866800000001",
            "name": "Training Assessment Agent",
            "description": "Training and competency assessment assistant",
            "prompt_info": {"prompt": "# Role\nYou are the Training Assessment Agent..."},
            "workflow_id_list": [
                "738958910358870001", "738958910358870002", "738958910358870003",
            ],
        },
    },
    "/v1/bots/7342866800000001/versions": {
        "code": 0, "msg": "",
        "data": {"items": [{"version": "1", "publish_status": "published_online"}]},
    },
}
# make every mock workflow id reusable
for _wid in ("738958910358870002", "738958910358870003"):
    MOCK_RESPONSES["/v1/workflows/" + _wid] = MOCK_RESPONSES[
        "/v1/workflows/738958910358870001"]
    MOCK_RESPONSES["/v1/workflows/" + _wid + "/versions"] = MOCK_RESPONSES[
        "/v1/workflows/738958910358870001/versions"]


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Export a Coze project's structure to local JSON files.")
    ap.add_argument("--workspace", help="workspace_id (the number after /w/ in the URL)")
    ap.add_argument("--bot-id", help="agent/bot ID (the number after /bot/ in the URL)")
    ap.add_argument("--base", help="API base; defaults to COZE_API_BASE or https://api.coze.cn")
    ap.add_argument("--out", help="output directory; defaults to ../coze-export/<date>")
    ap.add_argument("--mock", action="store_true",
                    help="run against canned sample data; needs no token")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    env_file = load_env(os.path.join(here, ".."))

    base = args.base or os.environ.get("COZE_API_BASE") or "https://api.coze.cn"
    token = os.environ.get("COZE_API_TOKEN") or ""
    bot_id = args.bot_id or os.environ.get("COZE_BOT_ID") or ""
    workspace_id = args.workspace or os.environ.get("COZE_WORKSPACE_ID") or ""

    if args.mock:
        workspace_id = workspace_id or "758146547629590001"
        bot_id = bot_id or "7342866800000001"
        if not args.out:
            args.out = os.path.join(here, "..", "coze-export", "MOCK")

    if not token and not args.mock:
        print("No COZE_API_TOKEN found.")
        if env_file:
            print("  Looked at: %s -- the file exists but has no COZE_API_TOKEN." % env_file)
        else:
            print("  No .env file found walking up from %s" % here)
        print("  Create one with:\n      COZE_API_TOKEN=pat_xxxxxxxx\n"
              "      COZE_BOT_ID=7xxxxxxxxxxxxx\n"
              "      COZE_API_BASE=https://api.coze.cn\n"
              "  (the token must be a Personal Access Token with these scopes:\n"
              "   listWorkflow, getMetaData, getMetadata, Bot.listVersion)")
        sys.exit(2)

    if not workspace_id:
        print("No workspace_id. Pass --workspace, or set COZE_WORKSPACE_ID.")
        print("  Find it in the workspace URL: https://code.coze.cn/w/<THIS>/projects")
        sys.exit(2)

    out_dir = os.path.abspath(args.out or os.path.join(
        here, "..", "coze-export", "export"))
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 68)
    print("Coze project export%s" % ("  [MOCK MODE]" if args.mock else ""))
    print("=" * 68)
    print("  base         : %s" % base)
    print("  workspace_id : %s" % workspace_id)
    print("  bot_id       : %s" % (bot_id or "(none)"))
    print("  env file     : %s" % (env_file or "(not found)"))
    print("  output       : %s" % out_dir)
    print("")

    client = CozeClient(base, token, mock=args.mock)
    report, wf_index = collect(client, workspace_id, bot_id, out_dir)
    summary = write_summary(out_dir, report, wf_index, {
        "base": base, "workspace_id": workspace_id,
        "bot_id": bot_id, "mock": args.mock,
    })

    for label, status, note, fn in report:
        mark = {"ok": "OK  ", "FAILED": "FAIL", "note": "note",
                "skipped": "skip"}.get(status, "?   ")
        print("  [%s] %-28s %s" % (mark, label, note))

    print("")
    print("  API calls made: %d" % len(client.calls))
    print("  Summary written: %s" % summary)
    print("  Output dir      : %s" % out_dir)
    print("")

    failed = [r for r in report if r[1] == "FAILED"]
    if failed:
        print("  %d step(s) failed. Re-run with the raw body visible:" % len(failed))
        for label, _, note, _ in failed:
            print("    - %s : %s" % (label.strip(), note))
        print("")
        print("  If the message says 4101, the PAT is missing a scope.")
        return 1

    print("  Next: open SUMMARY.md, then diff agent/config.draft.json against")
    print("  agent/config.published.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
