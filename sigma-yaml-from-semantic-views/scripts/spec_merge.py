"""
Merge one report (its page(s) + elements + layout) into an existing Sigma workbook document, keeping every other page.

Why: PUT /v2/workbooks/{id}/spec REPLACES the whole workbook. To keep a multi-page workbook, read the current
document (GET ...?format=json), merge, then PUT the merged document.

Rules:
  * A page of the report file whose NAME already exists in the workbook is REPLACED: the old page, every element
    placed in it (any depth of the layout, e.g. inside tabbed containers) and its <Page> layout node are removed.
  * Pages that don't exist yet are APPENDED (new tabs of the workbook).
  * All other pages, elements, settings and the workbook name are kept untouched.
  * Element ids, control ids and page ids must be unique in the whole workbook -> collisions are reported, never
    silently renamed (formulas/SQL reference them).
"""
import copy
import json
import re
import xml.etree.ElementTree as ET

PLACEHOLDER = "REPLACE_WITH_SIGMA_CONNECTION_ID"


class MergeError(Exception):
    pass


def load_report_file(path, connection_id=None):
    text = open(path, encoding="utf-8").read()
    if connection_id:
        text = text.replace(PLACEHOLDER, connection_id)
    if path.lower().endswith(".json"):
        data = json.loads(text)
    else:
        try:
            import yaml  # PyYAML
        except ImportError:
            raise MergeError("reading .yaml needs PyYAML: run  python -m pip install --user pyyaml  "
                             "(or give the report as .json)")
        data = yaml.safe_load(text)
    doc = data.get("document", data)
    for k in ("elements", "pages", "layout"):
        if k not in doc:
            raise MergeError(f"report file has no document.{k}")
    return doc


def _parse_layout(layout):
    """Layout is several sibling <Page> nodes (no single root). Returns list of Page elements."""
    body = re.sub(r"^\s*<\?xml[^>]*\?>", "", layout or "").strip()
    if not body:
        return []
    root = ET.fromstring(f"<Root>{body}</Root>")
    return [p for p in root if p.tag == "Page"]


def _layout_to_text(pages):
    parts = ['<?xml version="1.0" encoding="utf-8"?>']
    for p in pages:
        ET.indent(p, space="  ")
        parts.append(ET.tostring(p, encoding="unicode"))
    return "\n".join(parts) + "\n"


def _element_ids_in(page_node):
    return {n.get("elementId") for n in page_node.iter() if n.get("elementId")}


def _control_ids(elements):
    return {e.get("controlId") for e in elements if e.get("kind") == "control" and e.get("controlId")}


def merge(existing_doc, report_doc):
    cur = copy.deepcopy(existing_doc or {})
    cur.setdefault("schemaVersion", 1)
    cur_pages = cur.get("pages") or []
    cur_elements = cur.get("elements") or []
    cur_layout = _parse_layout(cur.get("layout"))
    layout_by_id = {p.get("id"): p for p in cur_layout}

    rep_pages = report_doc["pages"]
    rep_layout = _parse_layout(report_doc["layout"])
    rep_layout_ids = {p.get("id") for p in rep_layout}
    for p in rep_pages:
        if p["id"] not in rep_layout_ids:
            raise MergeError(f"report page '{p['name']}' ({p['id']}) has no <Page id=\"{p['id']}\"> in its layout")

    replaced, added, removed_elements = [], [], set()
    drop_page_ids = set()
    for rp in rep_pages:
        for cp in cur_pages:
            if cp.get("name", "").strip().lower() == rp["name"].strip().lower():
                drop_page_ids.add(cp["id"])
                node = layout_by_id.get(cp["id"])
                if node is not None:
                    removed_elements |= _element_ids_in(node)
                replaced.append(rp["name"])
                break
        else:
            added.append(rp["name"])

    kept_pages = [p for p in cur_pages if p["id"] not in drop_page_ids]
    kept_elements = [e for e in cur_elements if e.get("id") not in removed_elements]
    kept_layout = [p for p in cur_layout if p.get("id") not in drop_page_ids]

    # collisions with what stays in the workbook
    problems = []
    kept_el_ids = {e.get("id") for e in kept_elements}
    for e in report_doc["elements"]:
        if e.get("id") in kept_el_ids:
            problems.append(f"element id '{e['id']}' already used by another page")
    for c in sorted(_control_ids(report_doc["elements"]) & _control_ids(kept_elements)):
        problems.append(f"controlId '{c}' already used by another page (control ids are workbook-wide)")
    kept_page_ids = {p["id"] for p in kept_pages}
    for p in rep_pages:
        if p["id"] in kept_page_ids:
            problems.append(f"page id '{p['id']}' already used by page "
                            f"'{next(x['name'] for x in kept_pages if x['id'] == p['id'])}'")
    if problems:
        raise MergeError("id collisions - prefix the report's ids with a page slug and regenerate:\n  - "
                         + "\n  - ".join(problems))

    cur["pages"] = kept_pages + copy.deepcopy(rep_pages)
    cur["elements"] = kept_elements + copy.deepcopy(report_doc["elements"])
    cur["layout"] = _layout_to_text(kept_layout + rep_layout)
    if "settings" not in cur and "settings" in report_doc:
        cur["settings"] = copy.deepcopy(report_doc["settings"])
    summary = {"replaced_pages": replaced, "added_pages": added, "kept_pages": [p["name"] for p in kept_pages],
               "removed_elements": len(removed_elements), "kept_elements": len(kept_elements),
               "report_elements": len(report_doc["elements"])}
    return cur, summary
