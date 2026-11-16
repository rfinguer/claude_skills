"""Generate the Sigma Workbooks-as-Code YAML for the Sample Dashboard 'Activity' page (Jira PROJ-275).
usage: python -I gen_yaml.py <src_dir> <out_dir>
Schema checked against Sigma's public OpenAPI (PUT /v2/workbooks/{id}/spec).
"""
import sys, os

src, out = sys.argv[1], sys.argv[2]

# ---- custom SQL (control values are injected by Sigma: {{...}}) ----
REL = "{{act-relative-date}}"
START = "TRY_TO_DATE(LEFT(TO_VARCHAR({{#formula [act-date-range].start}}), 10))"
END = "TRY_TO_DATE(LEFT(TO_VARCHAR({{#formula [act-date-range].end}}), 10))"
act_sql = open(os.path.join(src, "activity.sql.tpl"), encoding="utf-8").read() \
    .replace("__REL__", REL).replace("__START__", START).replace("__END__", END)
wk_sql = open(os.path.join(src, "weekly.sql.tpl"), encoding="utf-8").read()
open(os.path.join(out, "activity_base.sql"), "w", encoding="utf-8").write(act_sql)
open(os.path.join(out, "activity_weekly.sql"), "w", encoding="utf-8").write(wk_sql)

PCT1, PCT2, PCT4 = ",.1%", ",.2%", ",.4f"
INT, USD0 = ",.0f", "$,.0f"
RED_WHITE_GREEN = ["#F8696B", "#FFFFFF", "#63BE7B"]
GREEN_WHITE_RED = ["#63BE7B", "#FFFFFF", "#F8696B"]
RED_YELLOW_GREEN = ["#F8696B", "#FFEB84", "#63BE7B"]
GREY = ["#E6E6E6", "#E6E6E6"]

# SQL column -> Sigma display name (names must not contain '/': Sigma reads [a/b] as element/column)
DIMS = [("ENTITY_ID", "Entity ID"), ("ENTITY_NAME", "Entity Name"), ("REGION", "Region"),
        ("STATUS", "Status"), ("STATUS_QTR", "QTR Status"), ("STATUS_YTD", "YTD Status"),
        ("ROLLUP", "Rollup"), ("ROLLUP_ENTITY_NAME", "Rollup Entity"), ("LEVEL_1", "LEVEL_1"), ("LEVEL_2", "LEVEL_2"),
        ("LEVEL_3", "LEVEL_3")]
ACT_ONLY_DIMS = [("FOCUS_ENTITY_FLAG", "Focus Entity Flag"), ("PERIOD_START", "Period Start"),
                 ("PERIOD_END", "Period End")]
ACT_BASES = ["ITEMS", "SNAPSHOT_ITEMS", "TREND_ITEMS", "TREND_GOAL_ITEMS", "EXPOSURE_NUM",
             "LIST_PRICE_AMT", "UTIL_ACTUAL_ITEMS", "UTIL_GOAL_ITEMS", "NEW_PRICE_T30", "PRIOR_PRICE_T30",
             "NEW_GROWTH_GOAL_T30", "NEW_PRIOR_GOAL_T30", "RPT_GROWTH_GOAL_T30", "RPT_PRIOR_GOAL_T30",
             "GROSS_ORDERS", "CANCELS", "REJECTS", "EXITS", "NET_EXITS", "RENEWALS"]
WK_BASES = ["NUM_NET_CONVERSIONS", "NUM_VISITS", "NUM_LEADS", "NUM_WEEKLY_AVAILABLE_ITEMS", "NUM_NET_CONVERSIONS_SAME_WEEK_PY",
            "NUM_VISITS_SAME_WEEK_PY", "NUM_LEADS_SAME_WEEK_PY", "NUM_WEEKLY_AVAILABLE_ITEMS_SAME_WEEK_PY"]

HIER = ('Switch([act-hierarchy], "Rollup", [Rollup], "LEVEL_1", [LEVEL_1], "LEVEL_2", [LEVEL_2], "Level 3", [LEVEL_3], "Region", [Region], '
        '"Status", [QTR Status], "Rollup Entity", [Rollup Entity], "Entity", [Entity Name], [Region])')

# hidden helpers (DAX building blocks), recomputed per group
HELPERS = [
    ("h Items", "Sum([ITEMS])", INT),                                   # SUM(DimItem[Items]) = [# Items]
    ("h Gross Order", "Zn(Sum([GROSS_ORDERS]))", INT),
    ("h Cancel", "Zn(Sum([CANCELS]))", INT),
    ("h Reject", "Zn(Sum([REJECTS]))", INT),
    ("h Net Order", "[h Gross Order] - [h Cancel] - [h Reject]", INT),
    ("h Exits", "Sum([EXITS])", INT),
    ("h Net Exits", "Sum([NET_EXITS])", INT),
    ("h Renewals", "Sum([RENEWALS])", INT),
    ("h Trend", "Sum([TREND_ITEMS]) / Sum([SNAPSHOT_ITEMS])", PCT1),          # [<30 Trend]
    ("h Goal Adj", "Sum([TREND_GOAL_ITEMS]) / [h Items]", PCT1),           # [<30 Goal Adjusted]
    ("h Lt30 Var Pct", "[h Trend] - [h Goal Adj]", PCT1),                           # [<30 Goal Var %]
    ("h Lt30 Var Num", "[h Lt30 Var Pct] * [h Items]", INT),                        # [<30 Var #]
    ("h Price per Item", "Sum([LIST_PRICE_AMT]) / [h Items]", "$,.2f"),                      # [Price per Item]
    ("h Util Var", "(Sum([UTIL_ACTUAL_ITEMS]) - Sum([UTIL_GOAL_ITEMS])) / [h Items]", PCT1),  # [Util Var %]
    ("h Price Var",                                                                  # [% Price Growth Var (Simple Avg)]
     "Zn((Sum([NEW_PRICE_T30]) - Sum([PRIOR_PRICE_T30])) / Sum([PRIOR_PRICE_T30]))"
     " - (Zn(Sum([NEW_GROWTH_GOAL_T30]) / Sum([NEW_PRIOR_GOAL_T30])) + Zn(Sum([RPT_GROWTH_GOAL_T30]) / Sum([RPT_PRIOR_GOAL_T30]))) / 2",
     PCT1),
]
# visible columns: (display name as in Power BI, DAX measure, formula, format)
M = {
    "Items": ("Sum(DimItem[Items])", "[h Items]", INT),
    "<30 Goal Var %": ("<30 Goal Var %", "[h Lt30 Var Pct]", PCT1),
    "<30 Var #": ("<30 Var #", "[h Lt30 Var Num]", INT),
    "Proj $ Var": ("Proj $ Var", "[h Price per Item] * [h Lt30 Var Num]", USD0),
    "Total Exposure": ("Total Exposure", "Sum([EXPOSURE_NUM]) / [h Items]", PCT1),
    "Gross Order": ("Gross Order", "[h Gross Order]", INT),
    "Gross Order %": ("Gross Order %", "[h Gross Order] / [h Items]", PCT1),
    "Cancel": ("Cancel", "[h Cancel]", INT),
    "Reject": ("Reject", "[h Reject]", INT),
    "% Cancel/Reject out of Gross Orders": ("% Cancel/Reject out of Gross Orders", "([h Cancel] + [h Reject]) / [h Gross Order]", PCT1),
    "Net Order": ("Net Order", "[h Net Order]", INT),
    "Net Order %": ("Net Order %", "[h Net Order] / [h Items]", PCT1),
    "Exit": ("Exits", "[h Exits]", INT),
    "Net Exit": ("Net Exits", "[h Net Exits]", INT),
    "Exits": ("Exits", "[h Exits]", INT),
    "Net Exits": ("Net Exits", "[h Net Exits]", INT),
    "Net/Net": ("Net/Net", "[h Net Order] - Zn([h Exits])", INT),
    "Net/Net %": ("Net/Net %", "([h Net Order] - Zn([h Exits])) / [h Items]", PCT1),
    "Net/Net (Net Exit)": ("Net/Net (Net Exits)", "[h Net Order] - Zn([h Net Exits])", INT),
    "Net/Net % (Net Exit)": ("Net/Net % (Net Exits)", "([h Net Order] - Zn([h Net Exits])) / [h Items]", PCT1),
    "Net/Net (Net Exits)": ("Net/Net (Net Exits)", "[h Net Order] - Zn([h Net Exits])", INT),
    "Net/Net % (Net Exits)": ("Net/Net % (Net Exits)", "([h Net Order] - Zn([h Net Exits])) / [h Items]", PCT1),
    "Renewals": ("Renewals", "[h Renewals]", INT),
    "Renew %": ("Renew %", "[h Renewals] / [h Items]", PCT1),
    "Cancel %": ("% Cancel out of Items", "[h Cancel] / [h Items]", PCT1),
    "Reject %": ("% Reject out of Items", "[h Reject] / [h Items]", PCT1),
    "Exit %": ("% Exit out of Items", "[h Exits] / [h Items]", PCT1),
    "Cancel & Reject": ("% Cancel/Reject out of Gross Orders", "([h Cancel] + [h Reject]) / [h Gross Order]", PCT1),
    "% Renew/Exit Ratio": ("% Renew/Exit Ratio", "[h Renewals] / [h Exits]", PCT1),
    "Weighted Score": ("Weighted Score",
                                        "Zn([h Util Var]) * [act-w-util] + Zn([h Lt30 Var Pct]) * [act-w-trend] + Zn([h Price Var]) * [act-w-price]",
                                        PCT4),
}

# Power BI column order + conditional formatting (PROJ-275)
ACTIVITY_COLS = ["Items", "<30 Goal Var %", "<30 Var #", "Proj $ Var", "Total Exposure", "Gross Order", "Gross Order %",
                 "Cancel", "Reject", "% Cancel/Reject out of Gross Orders", "Net Order", "Net Order %", "Exit", "Net Exit",
                 "Net/Net", "Net/Net %", "Net/Net (Net Exit)", "Net/Net % (Net Exit)", "Renewals", "Renew %"]
ACTIVITY_CF = [("backgroundScale", ["<30 Var #"], GREY),
               ("backgroundScale", ["<30 Goal Var %"], RED_WHITE_GREEN),
               ("backgroundScale", ["Total Exposure"], GREEN_WHITE_RED),
               ("backgroundScale", ["Gross Order %"], RED_WHITE_GREEN),
               ("backgroundScale", ["Net Order %"], RED_WHITE_GREEN),
               ("backgroundScale", ["Renew %"], RED_WHITE_GREEN),
               ("backgroundScale", ["Net/Net %"], RED_WHITE_GREEN),
               ("backgroundScale", ["% Cancel/Reject out of Gross Orders"], GREEN_WHITE_RED),
               ("backgroundScale", ["Net/Net % (Net Exit)"], RED_WHITE_GREEN)]
APPS_COLS = ["Weighted Score", "Items", "Gross Order", "Cancel", "Reject", "Net Order", "Renewals",
             "Exits", "Net Exits", "Net/Net", "Net/Net (Net Exits)", "Gross Order %", "Cancel %", "Reject %",
             "Net Order %", "Renew %", "Exit %", "Net/Net %", "Net/Net % (Net Exits)", "Cancel & Reject",
             "% Renew/Exit Ratio"]
APPS_CF = [("backgroundScale", ["Net Order %", "Net/Net %", "Net Order", "Net/Net", "Net/Net (Net Exits)",
                                "Net/Net % (Net Exits)"], GREY),
           ("backgroundScale", ["Weighted Score"], RED_YELLOW_GREEN),
           ("fontScale", ["Weighted Score"], RED_YELLOW_GREEN)]


def q(s):
    return "'" + s.replace("'", "''") + "'"


def indent(text, n):
    pad = " " * n
    return "\n".join(pad + l if l else l for l in text.split("\n"))


def base_columns(L, prefix, dims, bases, ids):
    for col, label in dims:
        cid = f"{prefix}d_{col.lower()}"
        ids[label] = cid
        L += [f"        - id: {cid}", f"          formula: '[Custom SQL/{col}]'", f"          name: {label}", "          hidden: true"]
    for col in bases:
        L += [f"        - id: {prefix}b_{col.lower()}", f"          formula: '[Custom SQL/{col}]'", f"          name: {col}",
              "          hidden: true"]


def table_element(eid, name, prefix, cols, cfs, ids):
    L = [f"    - id: {eid}", "      kind: table", f"      name: {name}", "      source:",
         "        connectionId: REPLACE_WITH_SIGMA_CONNECTION_ID", "        kind: sql", "        statement: |-",
         indent(act_sql.rstrip(), 10), "      columns:", "        # ---- additive bases from SEMANTIC_VIEW queries (hidden) ----"]
    base_columns(L, prefix, DIMS + ACT_ONLY_DIMS, ACT_BASES, ids)
    L += ["        # ---- field parameter z_Fields_PropHierarchy (control act-hierarchy) ----",
          f"        - id: {prefix}g_hier", f"          formula: {q(HIER)}", "          name: Hierarchy"]
    calc_ids = []
    L.append("        # ---- DAX building blocks (hidden) ----")
    for i, (n, f, fmt) in enumerate(HELPERS):
        cid = f"{prefix}h{i:02d}"
        calc_ids.append(cid)
        L += [f"        - id: {cid}", f"          formula: {q(f)}", f"          name: {q(n)}", "          hidden: true",
              "          format:", "            kind: number", f"            formatString: {q(fmt)}"]
    L.append("        # ---- visible measures (Power BI display name; description = DAX measure) ----")
    vis = {}
    for i, n in enumerate(cols):
        dax, f, fmt = M[n]
        cid = f"{prefix}m{i:02d}"
        vis[n] = cid
        calc_ids.append(cid)
        L += [f"        - id: {cid}", f"          formula: {q(f)}", f"          name: {q(n)}",
              f"          description: {q('DAX measure [' + dax + ']')}",
              "          format:", "            kind: number", f"            formatString: {q(fmt)}"]
    L += ["      groupings:", f"        - id: {prefix}grp_h", "          groupBy:", f"            - {prefix}g_hier",
          "          calculations:"] + [f"            - {c}" for c in calc_ids]
    L += ["      order:", f"        - {prefix}g_hier"] + [f"        - {vis[n]}" for n in cols]
    L.append("      conditionalFormats:")
    for typ, names, scheme in cfs:
        L += [f"        - type: {typ}", "          columnIds:"] + [f"            - {vis[n]}" for n in names]
        L += ["          scheme:"] + [f"            - '{c}'" for c in scheme]
    L += ["      tableComponents:", "        summaryBar: hidden", "      tableStyle:", "        preset: presentation",
          "        cellSpacing: small", "        textStyles:", "          header:", "            backgroundColor: '#0070C0'",
          "            color: '#FFFFFF'", "      frozenColumn:", f"        columnId: {prefix}g_hier"]
    return "\n".join(L)


act_ids, apps_ids, wk_ids = {}, {}, {}
act_yaml = table_element("act_table1", "Activity Table", "at_", ACTIVITY_COLS, ACTIVITY_CF, act_ids)
apps_yaml = table_element("act_apps01", "Apps Table", "ap_", APPS_COLS, APPS_CF, apps_ids)

# ---- weekly data (hidden page) + combo chart ----
W = ["    - id: wk_data001", "      kind: table", "      name: Activity Weekly Data", "      source:",
     "        connectionId: REPLACE_WITH_SIGMA_CONNECTION_ID", "        kind: sql", "        statement: |-",
     indent(wk_sql.rstrip(), 10), "      columns:"]
base_columns(W, "wk_", DIMS, [], wk_ids)
W = [l for l in W if l != "          hidden: true"]  # visible on the data page
W += ["        - id: wk_weekend", "          formula: '[Custom SQL/WEEK_ENDING]'", "          name: WeekEnding"]
for col in WK_BASES:
    W += [f"        - id: wk_b_{col.lower()}", f"          formula: '[Custom SQL/{col}]'", f"          name: {col}"]
wk_yaml = "\n".join(W)

CH = [("ch_c01", "Closing Ratio CY", "Sum([NUM_NET_CONVERSIONS]) / Sum([NUM_VISITS])", PCT2, "% Closing Ratio"),
      ("ch_c02", "Closing Ratio PY", "Sum([NUM_NET_CONVERSIONS_SAME_WEEK_PY]) / Sum([NUM_VISITS_SAME_WEEK_PY])", PCT2,
       "% Closing Ratio Same Week PY"),
      ("ch_c03", "% Closing Ratio Weekly YoY Chg (1st Axis)", "([Closing Ratio CY] - [Closing Ratio PY]) / [Closing Ratio PY]",
       PCT2, "% Closing Ratio Weekly YoY Chg"),
      ("ch_c04", "h Leads per EU", "Sum([NUM_LEADS]) / Sum([NUM_WEEKLY_AVAILABLE_ITEMS])", ",.2f", "# Leads per Available Item"),
      ("ch_c05", "h Leads per EU PY", "Sum([NUM_LEADS_SAME_WEEK_PY]) / Sum([NUM_WEEKLY_AVAILABLE_ITEMS_SAME_WEEK_PY])", ",.2f",
       "# Leads per Available Item Same Week PY"),
      ("ch_c06", "% Leads per Available Item Var", "([h Leads per EU] - [h Leads per EU PY]) / [h Leads per EU PY]", PCT2,
       "% Leads per Available Item Var"),
      ("ch_c07", "h Visits per EU", "Sum([NUM_VISITS]) / Sum([NUM_WEEKLY_AVAILABLE_ITEMS])", ",.2f", "# Visits per Available Item"),
      ("ch_c08", "h Visits per EU PY", "Sum([NUM_VISITS_SAME_WEEK_PY]) / Sum([NUM_WEEKLY_AVAILABLE_ITEMS_SAME_WEEK_PY])", ",.2f",
       "# Visits per Available Item Same Week PY"),
      ("ch_c09", "% Visits per Available Item Var", "([h Visits per EU] - [h Visits per EU PY]) / [h Visits per EU PY]", PCT2,
       "% Visits per Available Item Var")]
C = ["    - id: act_chart1", "      kind: combo-chart", "      name: Leads & Visits per Available Item", "      source:",
     "        kind: table", "        elementId: wk_data001", "      columns:", "        - id: ch_week01",
     "          formula: '[Activity Weekly Data/WeekEnding]'", "          name: WeekEnding"]
# child element: a bare [X] is the chart's OWN column -> paprice columns are [<paprice name>/X]
import re
_wk_re = re.compile(r"\[(" + "|".join(map(re.escape, WK_BASES)) + r")\]")
CH = [(cid, n, _wk_re.sub(lambda m: f"[Activity Weekly Data/{m.group(1)}]", f), fmt, dax) for cid, n, f, fmt, dax in CH]
for cid, n, f, fmt, dax in CH:
    C += [f"        - id: {cid}", f"          formula: {q(f)}", f"          name: {q(n)}",
          f"          description: {q('DAX measure [' + dax + ']')}", "          format:", "            kind: number",
          f"            formatString: {q(fmt)}"]
C += ["      xAxis:", "        columnId: ch_week01", "      yAxis:", "        columnIds:", "          - ch_c03",
      "          - columnId: ch_c06", "            type: line", "          - columnId: ch_c09", "            type: line",
      "      yAxis2:", "        columnIds:", "          - ch_c06", "          - ch_c09",
      "      tooltip:", "        columns:", "          - id: ch_c01", "          - id: ch_c02"]
chart_yaml = "\n".join(C)


# ---- controls ----
def manual_list(eid, cid, label, values, default, valueType="text"):
    L = [f"    - id: {eid}", "      kind: control", f"      controlId: {cid}", f"      name: {q(label)}",
         "      controlType: list", "      selectionMode: single", "      requiredInput: required", "      source:",
         "        kind: manual", f"        valueType: {valueType}", "        values:"]
    L += [f"          - {q(v)}" for v in values]
    L.append(f"      value: {q(default)}")
    return "\n".join(L)


def slider(eid, cid, label, value):
    return "\n".join([f"    - id: {eid}", "      kind: control", f"      controlId: {cid}", f"      name: {q(label)}",
                      "      controlType: slider", "      mode: '='", "      valueType: number", "      low: 0",
                      "      high: 1.05", "      step: 0.05", f"      value: {value}"])


def filter_list(eid, cid, label, col_label, mode="include", values=None, targets=("act", "apps", "wk")):
    L = [f"    - id: {eid}", "      kind: control", f"      controlId: {cid}", f"      name: {q(label)}",
         "      controlType: list", f"      mode: {mode}", "      selectionMode: multiple"]
    L += (["      values:"] + [f"        - {q(v)}" for v in values]) if values else ["      values: []"]
    L += ["      source:", "        kind: source", "        source:", "          kind: table", "          elementId: act_table1",
          f"        columnId: {act_ids[col_label]}", "      filters:"]
    tmap = {"act": ("act_table1", act_ids), "apps": ("act_apps01", apps_ids), "wk": ("wk_data001", wk_ids)}
    for t in targets:
        el, ids = tmap[t]
        L += ["        - source:", "            kind: table", f"            elementId: {el}", f"          columnId: {ids[col_label]}"]
    return "\n".join(L)


controls = "\n".join([
    "    # Slicer - RelativeDateLabel (saved selection Last 7 Days; anchored on DimCalendar[TodayDate] - 1 day, in the SQL)",
    manual_list("ctl_rel001", "act-relative-date", "Relative Date",
                ["Last 7 Days", "Last 14 Days", "Last 21 Days", "Last 30 Days", "WTD (1 Day Lag)", "MTD (1 Day Lag)",
                 "Yesterday"], "Last 7 Days"),
    "    # Slicer - Date (Between), intersected with the relative date inside the SQL",
    "\n".join(["    - id: ctl_date01", "      kind: control", "      controlId: act-date-range", "      name: Date",
               "      controlType: date-range", "      mode: between", "      includeNulls: when-no-value-is-selected"]),
    "    # Slicer - Hierarchy (field parameter z_Fields_PropHierarchy, saved selection Region)",
    manual_list("ctl_hier01", "act-hierarchy", "Hierarchy",
                ["Rollup", "LEVEL_1", "LEVEL_2", "Level 3", "Region", "Status", "Rollup Entity", "Entity"], "Region"),
    "    # Synced weight slicers (GENERATESERIES(0, 1.05, 0.05)); saved selections 0.2 / 0.2 / 0.6",
    slider("ctl_wutl01", "act-w-util", "Util Var Weight", 0.2),
    slider("ctl_wtrd01", "act-w-trend", "Trend Var Weight", 0.2),
    slider("ctl_wrnt01", "act-w-price", "MTD Price Var Weight", 0.6),
    "    # Filter pane (page + report level, PROJ-275)",
    filter_list("ctl_focus1", "act-focus", "Focus Entity Flag", "Focus Entity Flag", targets=("act", "apps")),
    filter_list("ctl_sytd01", "act-status-ytd", "YTD Status", "YTD Status"),
    filter_list("ctl_sqtr01", "act-status-qtr", "QTR Status", "QTR Status", mode="exclude", values=["Excluded"]),
    filter_list("ctl_lv1001", "act-level1", "LEVEL_1", "LEVEL_1"),
    filter_list("ctl_lv2001", "act-level2", "LEVEL_2", "LEVEL_2"),
    filter_list("ctl_lvl301", "act-level3", "Level 3", "LEVEL_3"),
    filter_list("ctl_reg001", "act-region", "Region", "Region"),
    filter_list("ctl_rlp001", "act-rollup-prop", "Rollup Entity", "Rollup Entity"),
    filter_list("ctl_prop01", "act-entity", "Entity Name", "Entity Name"),
])

texts = "\n".join([
    "    - id: act_title1", "      kind: text", "      body: '## **Activity**'", "      verticalAlign: center",
    "    - id: act_hdrutl", "      kind: text",
    "      body: '**<span style=\"color: #FFFFFF; background-color: #0070C0\">&nbsp;Utilization Trends&nbsp;</span>**'",
    "      verticalAlign: center",
    "    - id: act_hdrord", "      kind: text",
    "      body: '**<span style=\"color: #FFFFFF; background-color: #0070C0\">&nbsp;Order Activity&nbsp;</span>**'",
    "      verticalAlign: center",
    # Bookmark navigator 'Activity' (Table - Activity | Table - Apps | Chart View): the views are diffeprice element
    # kinds, so they are STACKED on the page, each under its own title (team rule: never a tabbed container).
    "    - id: act_sec001", "      kind: text", "      body: '### **Table - Activity**'", "      verticalAlign: center",
    "    - id: act_sec002", "      kind: text", "      body: '### **Table - Apps**'", "      verticalAlign: center",
    "    - id: act_sec003", "      kind: text", "      body: '### **Chart View**'", "      verticalAlign: center",
])

layout = """    <Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg_activity">
      <Element elementId="act_title1" gridColumn="1 / 7" gridRow="1 / 3"/>
      <Element elementId="ctl_rel001" gridColumn="7 / 12" gridRow="1 / 3"/>
      <Element elementId="ctl_date01" gridColumn="12 / 18" gridRow="1 / 3"/>
      <Element elementId="ctl_hier01" gridColumn="18 / 25" gridRow="1 / 3"/>
      <Element elementId="ctl_wutl01" gridColumn="1 / 5" gridRow="3 / 5"/>
      <Element elementId="ctl_wtrd01" gridColumn="5 / 9" gridRow="3 / 5"/>
      <Element elementId="ctl_wrnt01" gridColumn="9 / 13" gridRow="3 / 5"/>
      <Element elementId="ctl_focus1" gridColumn="13 / 17" gridRow="3 / 5"/>
      <Element elementId="ctl_sytd01" gridColumn="17 / 21" gridRow="3 / 5"/>
      <Element elementId="ctl_sqtr01" gridColumn="21 / 25" gridRow="3 / 5"/>
      <Element elementId="ctl_lv1001" gridColumn="1 / 5" gridRow="5 / 7"/>
      <Element elementId="ctl_lv2001" gridColumn="5 / 9" gridRow="5 / 7"/>
      <Element elementId="ctl_lvl301" gridColumn="9 / 13" gridRow="5 / 7"/>
      <Element elementId="ctl_reg001" gridColumn="13 / 17" gridRow="5 / 7"/>
      <Element elementId="ctl_rlp001" gridColumn="17 / 21" gridRow="5 / 7"/>
      <Element elementId="ctl_prop01" gridColumn="21 / 25" gridRow="5 / 7"/>
      <Element elementId="act_sec001" gridColumn="1 / 25" gridRow="7 / 8"/>
      <Element elementId="act_hdrutl" gridColumn="3 / 9" gridRow="8 / 9"/>
      <Element elementId="act_hdrord" gridColumn="9 / 25" gridRow="8 / 9"/>
      <Element elementId="act_table1" gridColumn="1 / 25" gridRow="9 / 40"/>
      <Element elementId="act_sec002" gridColumn="1 / 25" gridRow="40 / 41"/>
      <Element elementId="act_apps01" gridColumn="1 / 25" gridRow="41 / 72"/>
      <Element elementId="act_sec003" gridColumn="1 / 25" gridRow="72 / 73"/>
      <Element elementId="act_chart1" gridColumn="1 / 25" gridRow="73 / 100"/>
    </Page>
    <Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg_data001">
      <Element elementId="wk_data001" gridColumn="1 / 25" gridRow="1 / 30"/>
    </Page>"""

doc = f"""# Sigma Workbooks-as-Code spec - Sample Dashboard / page "Activity" (Jira PROJ-275)
# Source of truth: PROJ-275 report page specification + Power BI TMDL (Sample Dashboard TMDL).
# Data ONLY from Snowflake semantic views (custom SQL: SELECT ... FROM SEMANTIC_VIEW(...)):
#   MY_DB.MY_SCHEMA.TRANSACTIONS_SV  Gross Order (order date), Cancel/Reject (cancel date)
#   MY_DB.MY_SCHEMA.SNAPSHOT_SV         snapshot, exits, renewals, calendar, weekly chart
#   MY_DB.MY_SCHEMA.PRICING_SV       price growth (Weighted Score)
# The SQL returns ADDITIVE bases per entity; Sigma recomputes every DAX measure per hierarchy group,
# so totals / filtered groups match DAX (ratios are never averaged).
# Generated by src/gen_yaml.py - edit the generator, not this file.
#
# Power BI -> Sigma (PROJ-275):
#   Bookmark navigator (Table - Activity | Table - Apps | Chart View) -> the 3 views stacked (no tabbed container)
#   Activity Table / Apps Table / Leads & Visits per Available Item     -> act_table1 / act_apps01 / act_chart1
#   Slicer - RelativeDateLabel + Slicer - Date -> act-relative-date + act-date-range (used inside the SQL)
#   Slicer - Hierarchy (field parameter)       -> act-hierarchy (Switch() in column 'Hierarchy')
#   Util / Trend / MTD Price Var Weight slicers  -> sliders act-w-util / act-w-trend / act-w-price (0..1.05 step 0.05)
#   Filter pane: Focus Entity Flag, YTD Status, QTR Status (excludes Excluded), LEVEL_1, LEVEL_2, Level 3, Region,
#                Rollup Entity, Entity Name -> list controls
#   Locked/hidden filters (EntityID not blank, DimItem[ActiveFlag] = 1, xDaysAgo_1DayLag >= 0,
#   xYearsAgo_1DayLag 0..1, xWeeksAgo 1..52 on the chart) -> applied inside the SQL
name: Sample Dashboard - Activity
document:
  schemaVersion: 1
  elements:
{texts}
{controls}
{act_yaml}
{apps_yaml}
{wk_yaml}
{chart_yaml}
  pages:
    - id: pg_activity
      name: Activity
    - id: pg_data001
      name: Activity Data
      visibility: hidden
  settings:
    theme:
      overrides:
        hasCards: hidden
  kind: workbook
  layout: |
    <?xml version="1.0" encoding="utf-8"?>
{layout}
"""
open(os.path.join(out, "sample_activity.yaml"), "w", encoding="utf-8", newline="\n").write(doc)
print("ok", len(doc.splitlines()), "lines")
