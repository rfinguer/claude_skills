---
name: sigma-yaml-from-semantic-views
description: Rebuild a Power BI report page as a Sigma workbook YAML (Workbooks-as-Code) whose data comes from Snowflake Semantic Views, as one page (tab) of a multi-page Sigma workbook, then push it from the command line with each user's own API credentials (masked sign-in; only a 1-hour access token is cached), adding or replacing only that page. Reads the Jira ticket through the Atlassian MCP server. Starts by asking for the target workbook ID, the Jira ticket that describes the page, and the Power BI TMDL. Use whenever someone wants to recreate / migrate a Power BI page, visual, ticket spec (e.g. a Jira story describing a report page) or TMDL measures in Sigma; generate or fix a Sigma workbook spec YAML; import/push/apply a YAML into Sigma via the API (PUT /v2/workbooks/{id}/spec); or debug a Sigma spec import error (invalid value, dependency not found, yAxis2, verticalAlign...). Also use it for "Sigma on top of semantic views", "SEMANTIC_VIEW custom SQL in Sigma" or "import a YAML into Sigma".
---

# Power BI page → Sigma YAML on Snowflake Semantic Views

Goal: a Sigma workbook spec that (1) Sigma's importer accepts and (2) reproduces the Power BI page faithfully, i.e. the
same visuals, display names, filters, slicers, formatting and **numbers equal to the DAX**. Then push it with
`scripts/sigma_cli.py`.

**Where each part comes from (strict):**
- **Data = Snowflake only.** Every number, metric, dimension, filter and date logic comes from the semantic views in
  the user's Snowflake connection, mapped from the DAX in the **TMDL**. You decide, from the TMDL against the semantic
  views, what can go on the page and how it is computed.
- **Jira ticket = layout only.** Use it for what the page looks like: page title, visual types and order, which
  fields each visual shows and their display names, slicers/buttons and their defaults, bookmarks, text labels,
  colors and conditional formatting. Never take data logic from the ticket; when the ticket and the TMDL disagree on
  a calculation, the TMDL + semantic views win, and you list the difference in the report.

## Language

Talk to the user **in English** (messages, questions, the final report, the text in the Sigma windows), unless their
`config.local.json` has a `"language"` value (e.g. `"pt-BR"`): then use that language. Code, file content, commit
messages and anything written to the repository stay in English.

## Security rules (non-negotiable)

- Each user creates **their own** Sigma API client (Sigma > Administration > Developer Access) with permission to
  create/edit workbooks. Never reuse someone else's.
- Credentials are only typed at the CLI's **hidden prompt**. Never put the Client ID or Secret in a command line, a
  file, a chat, a YAML, `export`/`$env:` lines (they land in shell history), or a commit.
- If a secret shows up in plain text anywhere (terminal, history, chat), tell the user to **rotate it** in Sigma and
  to delete the shell history (PowerShell: `Remove-Item (Get-PSReadLineOption).HistorySavePath`).
- The scripts only send credentials over HTTPS to `*.sigmacomputing.com`. Don't weaken that check.
- **Session reuse (1 hour):** after a sign-in, only the short-lived **access token** (never the ID or Secret) is kept
  in the Windows Credential Manager, for the current Windows logon only. The next pushes within the hour don't ask
  again. The token is deleted when it expires, at Windows sign-out, on `sigma_cli.py logout`, or automatically if
  Sigma rejects it (and then the CLI asks to sign in again). `--no-cache` forces a fresh sign-in. On macOS/Linux
  nothing is cached.
- Keep `connectionId` out of the YAML that gets shared: use the placeholder `REPLACE_WITH_SIGMA_CONNECTION_ID`. The
  CLI substitutes it in memory.

## Keep the skill current (every run)

This skill lives in the **public** Git repository **https://github.com/rfinguer/claude_skills** (folder
`sigma-yaml-from-semantic-views/`). A team can also keep a **private fork** with its own settings and change log; then
that fork is the source of truth for the team.
- **Before step 0:** if the skill folder is inside a Git clone, run `git pull --ff-only` in the clone so you use the
  latest version. If the pull fails (no access, local changes, no network), say so in one line and go on.
- **Whenever you learn something new** while using the skill (a correction from the user, a new Sigma importer error
  and its fix, a spec key checked in the OpenAPI, a SEMANTIC_VIEW pattern, a workflow rule the user asks for),
  **update the skill and publish it in the same run**:
  1. Edit the right file: `SKILL.md` for workflow rules, `references/sigma-spec-gotchas.md` for Sigma spec errors
     and keys, `references/sql-patterns.md` for SQL / semantic view patterns, `references/sv-change-log.md` for
     semantic view changes (private forks only), `scripts/` for CLI behavior.
  2. **In a public repository write it generically**: never commit company names, database / schema / account /
     role names, hostnames, Jira keys or site names, people's names or e-mails, connection ids, data values,
     screenshots, or any secret. Use placeholders (`MY_DB.MY_SCHEMA`, `PROJ-123`, `<your-site>.atlassian.net`).
     Company values belong in `config.local.json` (or a private fork) only.
  3. Before committing, scan the diff for company identifiers and secrets (for example
     `git diff | grep -iE "<company>|secret|token|password|client_id"`). Never commit `config.local.json` or
     `preflight.local.json`.
  4. Commit with a short message that says what was learned (e.g. `sigma-yaml: grouped table sort must be per
     grouping level`), then `git push` with the user's own GitHub account. If they have no write access, push a
     branch to their fork and open a pull request with `gh pr create`.
  5. Tell the user in one line what changed and the commit or PR link.

## Configuration (once per user)

Settings live in **`config.local.json`** next to this file (git-ignored, so `git pull` never overwrites it).
`config.example.json` shows the keys.
- **If it is missing:** if the folder has a team defaults file (`config.team.json`, shipped by a private fork), copy
  it to `config.local.json` and tell the user in one line. Otherwise ask the user once, in the chat, for: the database
  and schema of the semantic views, the prefix of test copies to skip (e.g. `ZZ_`), the Snowflake account of their
  `snow connection list` entry, the Snowflake role to use, the Jira site (`<site>.atlassian.net`) and the Sigma API
  host of their org (e.g. `https://api.us.azure.sigmacomputing.com`). Write the file, then go on. Never put
  credentials in it.
- Afterwards read it at the start of every run and don't ask again. The user can ask to change it at any time.
- **Snowflake role:** run every Snowflake command with the user's own Snow CLI connection **and**
  `--role <snowflake_role>` (e.g. `snow sql -c <connection> --role <snowflake_role> -q ...`). Each person signs in with
  their **own** Snowflake login; never use or ask for someone else's credentials. If Snowflake says the role is not
  granted to the user, stop and tell them to ask their Snowflake administrator to grant `snowflake_role` to their
  Snowflake user.
- **Tell the user before the Snowflake sign-in.** If the connection uses single sign-on (`externalbrowser`), the first
  Snowflake command of a run (and any command after the login expired) opens the **default web browser** on the
  company / Snowflake sign-in page and waits. Before that first command, say: "A browser window may open to sign you
  in to Snowflake with your company account. Complete the sign-in there (and approve MFA if asked), then come back;
  I'll continue on my own." Run Snowflake commands with a generous timeout. If one seems stuck, remind the user to
  look for that browser window (it may be behind other windows).

## Workflow

### Preflight: make sure everything is installed and ready (before step 0)
Check each item yourself (run the command; don't ask the user to check). Report one line per item (ready / missing).
For every missing item, give the user **numbered, step-by-step instructions**, wait until they say it's done, and
check again. Don't start step 0 until all required items are ready.

**Remember what already passed:** keep the result in **`preflight.local.json`** next to this file (git-ignored),
e.g. `{"python": "2026-11-15", "snow_cli": "2026-11-15", "snowflake_role": "2026-11-15", ...}` with the date each item
passed (never credentials or values). On the next runs **skip the items already recorded** and only check the
missing ones; just say "preflight: ready (saved)". If a later step fails because of an item (e.g. the Snowflake
connection or the Sigma sign-in stops working), remove it from the file and check it again. Item 3's `git pull` is
not a check: it runs every time (see "Keep the skill current").

| # | Item | How to check | If missing, guide the user to |
|---|---|---|---|
| 0 | Model | the model you are running on (it is in your own system context) is **Claude Opus 5.5** (`claude-opus-5-5`) | stop and ask the user to switch to Opus 5.5 (the app's model selector, or `/model` in the CLI) and run the skill again; don't continue on another model. Check this every run (don't store it) |
| 0b | Company approval (if your company requires one) | the user confirms any internal approval to use Claude Code with the Snowflake connection is in place | tell them to follow their company's process (e.g. an access request) and wait for the approval before running the skill |
| 1 | Python 3.10+ with tkinter | `python --version`; `python -c "import tkinter"` | install Python from python.org (Windows: tick "Add python.exe to PATH" and "tcl/tk"), reopen the app |
| 2 | PyYAML (optional) | `python -c "import yaml"` | `python -m pip install --user pyyaml` (only needed to read `.yaml` reports; `.json` works without it) |
| 3 | Git + this repository | `git --version`; `git -C <skill folder> rev-parse --show-toplevel`, `git pull --ff-only` | install Git (git-scm.com); accept the GitHub invitation; clone + link as in the repository README |
| 4 | Snowflake CLI | `snow --version` | `python -m pip install --user snowflake-cli` (or `pipx install snowflake-cli`) |
| 5 | Snowflake connection | `snow connection list` shows an entry for `snowflake_account`; `snow sql -c <entry> --role <snowflake_role> -q "SELECT CURRENT_USER(), CURRENT_ROLE()"` | `snow connection add` with account `snowflake_account`, their own user (e-mail), authenticator `externalbrowser`; then sign in in the browser (warn them first: see "Tell the user before the Snowflake sign-in") |
| 6 | Snowflake role | the query above returns `snowflake_role` | ask their Snowflake administrator to grant the role to their Snowflake user; never use someone else's login |
| 7 | Semantic views readable | `SHOW SEMANTIC VIEWS IN SCHEMA <sv_database>.<sv_schema>` returns rows | same as item 6 (the role must have access) |
| 8 | Atlassian MCP | its tools are present (e.g. `getJiraIssue`) | set it up yourself (see step 1, "If it isn't connected"); the user only signs in |
| 9 | Sigma API client | ask: "Do you have your own Sigma API Client ID and Secret with permission to edit workbooks?" Then run `sigma_cli.py --gui --base-url <sigma_api_host> connections` (a sign-in window opens; this also caches the session for the push) | Sigma > Administration > **Developer Access** > **Create New** > API client, owner = themselves, permission to create/edit workbooks; copy the Client ID and Secret right away (the Secret is shown once); if they can't open Developer Access, a Sigma admin must create it for them. Never ask them to paste it in the chat |
| 10 | Sigma workbook access | the push's workbook list shows the target workbook (checked at the push, not stored) | the workbook must exist (create and save it once in Sigma) and they need **Can edit** on it (a 403 means no edit access) |
| 11 | TMDL file | the path from step 0 exists | export the TMDL from Power BI (or ask the report owner) |

### 0. Ask the user first (one message, before any work)
The workbook holds **several reports, one page (tab) each**, so every run targets an existing workbook and adds or
updates one page. **Never ask for the workbook**: the push always opens the searchable **workbook list** (don't pass
`--workbook-id`), and the user picks it there. A brand-new workbook must be created and saved once in the Sigma UI
first. Ask only for (skip what the user already gave, e.g. the ticket in the skill arguments):
1. **Jira ticket** (key or URL, e.g. `PROJ-275`) with the report page description. It is the **layout** spec. It is read
   through the **Atlassian MCP server** with the user's own Atlassian account (see step 1).
2. **The Power BI TMDL file**: always ask for its path. There is **no default path**; never assume one. It is
   **required**: with the semantic views it is the data spec (the DAX of every measure). Without it, stop and help
   the user get it (preflight item 11).
Taken from `config.local.json` (do NOT ask again; see "Configuration"):
- Semantic views: `sv_database`.`sv_schema` (skip copies whose name starts with `skip_sv_prefix`).
- Snow CLI connection: the user's own `snow connection list` entry for `snowflake_account`, used with
  `--role <snowflake_role>`.
- Jira site: `jira_site`.
- Sigma API host: `sigma_api_host` (pass it as `--base-url`).
Never ask for the Sigma Client ID/Secret in the chat. They type those only at the CLI's hidden prompt.

### 1. Collect the page spec
- **Jira ticket, through the Atlassian MCP server (v2, `https://mcp.atlassian.com/v2/mcp`):**
  - **Check that it is connected:** look for its tools, e.g. `getJiraIssue` and `getAccessibleAtlassianResources`
    (the tool names carry the server prefix, e.g. `mcp__atlassian__getJiraIssue`). If they are deferred, load them
    first.
  - **If it isn't connected, Claude sets it up itself** (the user never opens a terminal):
    1. Run `claude mcp list` and look for the Atlassian server (`https://mcp.atlassian.com/v2/mcp`). Organizations
       often already have the claude.ai connector **`claude.ai Atlassian MCP`**, shown as "Needs authentication".
    2. If no Atlassian server is listed, add it:
       `claude mcp add --transport http atlassian https://mcp.atlassian.com/v2/mcp`.
    3. Start the sign-in yourself, in the background: `claude mcp login "<server name from the list>"`. It opens the
       user's default browser on the OAuth 2.1 page (via claude.ai for a claude.ai connector). Tell the user: "a
       browser page opened: sign in with your own Atlassian account and click Accept". Signing in and granting
       consent are the user's: never type their password, and never ask for an Atlassian password or API token in
       the chat.
    4. Run `claude mcp list` again: the server should be "Connected". The tools only load in **a new Claude Code
       session** (the CLI says "available the next time you start Claude Code"), so ask the user to start a new
       session (or restart the app) and run the skill again.
    - Setup guide: https://support.atlassian.com/atlassian-ai-gateway/docs/get-started-with-the-atlassian-remote-mcp-server/
  - **Read the ticket (read-only tools only):**
    1. `cloudId`: the site hostname from the config (`jira_site`) works directly; otherwise call
       `getAccessibleAtlassianResources`.
    2. `getJiraIssue` with the `cloudId` and the key (e.g. `PROJ-271`) for the summary, description and attachments.
    3. **Always read the description AND every comment** (`listJiraIssueComments`, all pages until `isLast`, oldest
       first). Comments often change the spec: reviews ("Denied", "Approved") with notes, extra views, missing
       conditional formatting, custom sorts, "updated the screenshots". Build the layout from the description plus
       every comment, and when they conflict **the newest comment wins**. In the report, list which comments changed
       the layout. (In Atlassian MCP v2, if the tool is deferred: find it with `discover`, run it with `executeRead`.)
    4. Screenshots, if needed: `downloadJiraIssueAttachment` returns a short-lived URL and a command to save the
       file. Tell the user which file you will download first, save it in the scratchpad, then view it with Read.
  - Jira is read-only, with **one exception**: adding the gap comment of step 6 with `addOrEditJiraIssueComment`
    (a new comment only, after the user confirms the text). **Never** edit or delete comments, change fields,
    status, assignee or sprints, or call `createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`,
    `executeDestructive`...
  - Keep the ticket's **assignee** (`fields.assignee.accountId` and `displayName` from `getJiraIssue`) for step 6.
  - Take from the ticket **only the layout**: page title (= Sigma page name), visuals (type, order, grouping), the
    fields each one shows and their display names, slicers/buttons and their saved selections, bookmarks, text
    labels, colors and conditional formatting. Filters listed there tell you which filter controls the page needs;
    how they filter is checked in the TMDL / semantic views.
  - Don't take numbers, formulas or data rules from the ticket (see "Where each part comes from").
- **TMDL** (the data spec, with the semantic views): it has the DAX of every measure, the calculated tables (field parameters, what-if weights,
  ranking tables), the relationships (active/inactive, cross-filter direction) and the M partitions. It has **no
  report layout**. Extract the DAX of every measure on the page and of its dependencies (recursively).
- **Visual inventory** (PBIR export: page → visual → field, display name), if they have one.

### 2. Map DAX to the semantic views (and decide what goes on the page)
For every field the ticket's layout needs, find its DAX in the TMDL and its semantic view metric/dimension. Then
decide: **include** it when the semantic views support it (directly, or rebuilt from additive bases); **add a
public metric** when the base exists but isn't exposed and the user may change the semantic view (see "Changing a
semantic view"); otherwise **leave it out / empty** and report it in the Jira gap comment (step 6). Don't invent data
that isn't in Snowflake.
**Every name comes from the user's own Snowflake connection.** Semantic views, tables, dimensions, metrics and
facts are always discovered live with the user's Snow CLI connection (the `snow connection list` entry for
`snowflake_account`), so the user only sees objects their role can access. Never copy names from
`assets/example/` or `references/`: those are neutral placeholders (`SNAPSHOT_SV`, `DIM_ENTITY.ENTITY_ID`,
`NUM_ITEMS`...) that show the patterns, not real objects.
- `SHOW SEMANTIC VIEWS IN SCHEMA <sv_database>.<sv_schema>`. Skip names starting with `skip_sv_prefix` unless the
  user says otherwise. If the config has no database/schema yet, run `SHOW SEMANTIC VIEWS IN ACCOUNT` and let the
  user pick.
- **Read the YAML**, not just DESCRIBE: `SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('<db>.<schema>.<sv>')`.
  View-level (derived) metrics (e.g. a `NET_ORDERS = GROSS_ORDERS - CANCELS` metric) do **not** show up as table
  metrics in DESCRIBE.
  Their `synonyms` usually carry the DAX name.
- **Before saying a metric is missing, search every semantic view line by line** (e.g. `grep -n "^\s*- name:"` over the
  YAML of all of them, tables AND view-level metrics). The same DAX measure is often in a different SV than expected,
  and block-based regex parsing can silently skip entries. Only then report a real gap.
- Write SV deploy scripts to a file and run them with `snow sql -f`: inline shell commands that contain the `$$`
  delimiter are blocked by the shell safety checks.
- Constraints you will hit:
  - Private metrics (`H_*`, `access_modifier: private_access`) can't be queried.
  - FACTS can't be queried together with DIMENSIONS.
  - `PARTITION BY EXCLUDING` / ratio metrics at another grain may fail with "Multi-path in many-to-many".
- If a needed metric is missing or private, follow **"Changing a semantic view"** below.

#### Changing a semantic view (adding public metrics)
**Who may change a semantic view: any user whose Snowflake role owns it.** Check it live, every time, before
changing anything: `snow sql ... --role <snowflake_role> -q "SELECT CURRENT_ROLE()"` works, and
`SHOW GRANTS ON SEMANTIC VIEW <sv>` shows `OWNERSHIP` for that role. If the check passes, follow the steps below
(with the user's OK). If it fails, **don't change anything in Snowflake** (no `CREATE`/`ALTER`/`GRANT`, no
`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`, not even the `TRUE` validation): build the page with what the semantic views
support, leave the rest empty, and report it in the Jira comment (step 6). Never read the base tables directly to work
around a gap, and never change grants or roles.

When allowed:
1. Ask the user's OK, listing the metrics to add (name, expression, why).
2. **Read the YAML right before changing it** (`SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`): another user may have added
   metrics minutes ago, and a deploy from an old copy would silently delete them. Save it as the backup
   (`sv_backup/<SV>_BKP_<yyyymmdd_hhmm>.yaml`) and list its metric names.
3. **Only add** metrics (public, additive) and the private `H_*` helpers they need. Never rename, change or remove an
   existing one.
4. Validate with `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('<db>.<schema>', <yaml>, TRUE)` (from a script file:
   `snow sql -f`), record `SHOW GRANTS ON SEMANTIC VIEW`, deploy with `FALSE` right away, and compare the grants
   after the deploy: re-grant anything that disappeared.
5. Read the YAML again and check that **every metric from step 2 is still there** plus the new ones. Check the new
   metrics' numbers (totals vs. the source metric, per-entity rows summing to the total).
6. Append a line to `references/sv-change-log.md` (date, semantic view, metrics added, reason / ticket, the user's
   name) and publish it with the skill (see "Keep the skill current").

### 3. Design the custom SQL (the key decision)
Read `references/sql-patterns.md`. In short:
- **Return ADDITIVE bases per lowest grain** (usually one row per entity, e.g. store, customer or account) and let Sigma recompute every DAX
  measure per group. Never let Sigma average or sum ratios.
- **Rebuild ratio numerators exactly**: `ratio_metric * its_own_denominator` (e.g. `UTIL_PCT * NUM_ITEMS`).
  Check it: aggregate the bases at a higher grain and compare against the SV metric queried at that grain. The match
  must be exact (a difference of about 1e-9 is fine).
- **Keep each DAX date role** (`USERELATIONSHIP`). For example, orders by order date and cancellations by
  cancel date. Use one `SEMANTIC_VIEW()` subquery per role, then join each to a shared date window.
- Apply **hidden/locked report and page filters inside the SQL** (`WHERE` inside `SEMANTIC_VIEW`). Bi-directional
  relationships propagate: in DAX, a filter on an item dimension also restricts the entities.
- Relative-date slicers: anchor on the model calendar's "today" (e.g. `DIMCALENDAR.TODAYDATE - 1` for "1 Day Lag"),
  not `CURRENT_DATE`.
- Controls inside the SQL use Sigma's syntax:
  - single value: `{{control-id}}`
  - date range: `{{#formula [control-id].start}}` / `.end`
  - multi-select: `IN {{control-id}}`, guarded by `{{#formula ArrayLength([id])}} = 0`.
- Wrap dates defensively: `TRY_TO_DATE(LEFT(TO_VARCHAR(<placeholder>), 10))`.
- **Run every SQL in Snowflake** with the placeholders replaced by literals (each relative-date option, empty
  controls) before writing the YAML.

### 4. Write the YAML (one report = one page + an optional hidden data page)
Read `references/sigma-spec-gotchas.md`, and when unsure about a key **check the official schema** with
`scripts/sigma_schema_probe.py` (`download`, then `keys <k1,k2>` / `controls` / `elements`). Don't guess.
Multi-page rules: the report file only contains **its own** pages, and the CLI merges them into the workbook.
- **Page name** = the ticket's page title (e.g. `Activity`). A helper data page is named `<Page> Data`
  (e.g. `Activity Data`) with `visibility: hidden`.
- **Every element id, page id and controlId gets a page prefix** (e.g. `act_table1`, `act-date-range`). Control ids
  are workbook-wide, so two reports can't both use `date-range`. The CLI refuses collisions.
- Re-pushing the same report replaces its pages, matched by name. All other pages stay untouched.
Faithfulness checklist:
- Same columns in the same order as the ticket's layout. Column `name` = the display name from the ticket;
  `description` = `DAX measure [..]` from the TMDL.
- Formats taken from the DAX `formatString`.
- Bookmark navigator → **segmented control, NEVER a `tabbed-container`**: `controlType: segmented`, one value per
  bookmark button (`source: {kind: manual, valueType: text, values: [...]}`), `value` = the default bookmark.
  The button switches the view: build **one** element whose level/series/columns change with
  `If([<view-control>] = "<button>", ..., ...)` (e.g. a ranking page with "by Level 2" / "by Level 3" buttons → one table whose group, leader and rank
  columns switch between the two levels). Column names are static, so give switching columns a neutral name
  (`Level 2 | Level 3`).
  If the bookmarks show **different elements** (e.g. two tables with different columns and a chart), don't ask:
  **stack all the views on the page**, top to bottom in the navigator's button order, each under a text title with the
  button's name (e.g. `### **Table - Activity**`), and drop the button. Still no tabbed container.
  (Example: `assets/example/gen_yaml.py`, Activity page: Table - Activity / Table - Apps / Chart View stacked.)
- Field parameter → manual single-select list + `Switch([control], ...)` grouping column.
- What-if slicers → `slider` (low/high/step/value = GENERATESERIES and the saved selection).
- Filter pane fields → `list` controls targeting every element they filter (`mode: exclude` with values for "is not X").
- Conditional formatting gradients → `backgroundScale` / `fontScale` with `scheme: [min, mid, max]`.
- Combo chart with a secondary axis → series listed in `yAxis.columnIds` (with `type: line`) **and** in `yAxis2.columnIds`.
  Tooltip fields go in `tooltip.columns`.
- Generate the YAML from a script (see `assets/example/`) so you can regenerate after each fix. Never hand-edit
  1,000-line YAML.

### 5. Push and iterate: Claude runs it, the user never opens a terminal
Run the CLI **yourself** with `--gui` (Bash/PowerShell tool, `run_in_background`, and wait for the completion
notification). Native windows (always on top) pop up on the user's screen:
1. **Sign in**: the user types their own Client ID and Secret. Both are masked, kept in memory only, and sent only
   to the Sigma host. It's skipped while the 1-hour session token is still valid, so fix-and-push rounds don't ask
   again. If the user wants another account, run `logout` first.
2. **Connection**: a searchable list, shown only if the report still has `REPLACE_WITH_SIGMA_CONNECTION_ID` and you
   didn't pass `--connection-id`.
3. **Workbook**: a searchable list (always shown: never pass `--workbook-id` on the first push of a run; on a
   fix-and-push retry in the same run you may pass the id the user just picked).
4. **Confirm**: shows the current pages and what will be kept / added / replaced, plus the backup path, under a red
   warning that the push **publishes**. The user clicks **Publish** or **Cancel**.

**Every push PUBLISHES the workbook.** Sigma's API has no "save to draft" (checked in the OpenAPI: neither
`PUT .../spec` nor `PUT .../contents` has a draft option, and `GET /v2/workbooks/{id}/version-history` lists every
push as a published version). So:
- Before running the push, tell the user it will publish immediately, visible to everyone with access.
- If the user has a **Draft** open in the Sigma editor, it was made from an older version: after the push it shows
  old errors. Tell them to **discard the draft**, never to publish it (that would bring the old version back).
- A 403 means the API client's user has no **Can edit** on that workbook (not a spec error).
```
python <skill>/scripts/sigma_cli.py --gui --base-url https://<org-api-host>.sigmacomputing.com push --workbook-id <uuid> --yaml <report>.json --log last_push.txt
```
Before running it, tell the user: "a Sigma window will open on your screen; type your Client ID/Secret there".
Exit codes:
- `0`: applied, or a dry run.
- `2`: Sigma rejected the spec. The errors are printed; fix the generator, regenerate, run again (no new sign-in within the hour).
- `3`: the user cancelled or closed a window.
- `1`: any other error.
Never pass the credentials as arguments or environment variables, and never ask for them in the chat.
Use `--dry-run` to preview the page changes without pushing.

Manual alternative (the user's own terminal, hidden prompts instead of windows): the same command without `--gui`.

### 5b. Details of the push (adds or updates the page; the other pages are kept)
```
python -m pip install --user pyyaml          # once, to read .yaml reports (or give the report as .json)
python scripts/sigma_cli.py --base-url https://<your-org-api-host>.sigmacomputing.com push --workbook-id <uuid> --yaml <report>.yaml
```
- The user types their own Client ID/Secret at the hidden prompt. If they're missing, the CLI lists connections
  (`REPLACE_WITH_SIGMA_CONNECTION_ID` is replaced in memory) and workbooks.
- The CLI reads the current workbook (`GET /v2/workbooks/{id}/spec?format=json`) and saves a **local backup**
  (`backup_<id>_<timestamp>.json`). It shows which pages will be **kept / added / replaced** and asks before applying.
- It then PUTs the merged document. `PUT .../spec` replaces the whole workbook, which is why the merge is needed.
- To restore a backup: `push --replace-workbook --yaml backup_....json`.
- On a 400 nothing is changed. Sigma lists **one validation stage at a time** (element by element). Fix the generator,
  regenerate, press Enter in the same CLI session (the token is reused for about 1 hour).
- Other commands: `pages --workbook-id <id>` (list the tabs), `connections`, `workbooks`,
  `export --workbook-id <id> --out x.yaml`.
- `scripts/push_to_sigma.ps1` (no Python) **replaces the whole workbook**. Use it only for a single-page workbook.
- Run the CLI in a terminal the user controls (they type the secrets there). Never ask them to paste secrets into the
  chat.

### 6. Report honestly, and put the gaps in a Jira comment
- An accepted import only proves the **structure**. The SQL and the control substitution run when the workbook
  opens, so ask the user to open it and check every tab (and check it through the API export when possible).
- List what wasn't converted and why, and the data limitations (e.g. keys that don't join so a measure is empty).
- **Comment on the Jira ticket only when something has no solution in this run**, i.e. it stays missing or
  different after you did everything the user is allowed to do: the data isn't in Snowflake (no base to build a
  metric from), the user's role can't change the semantic view that would need a new metric, or Sigma has no
  equivalent feature (e.g. a color scale based on another column). If everything was solved (including by adding
  metrics), **don't comment**. If the user says not to comment, don't. Then write **one comment** that **mentions
  the assignee**:
  1. Draft it in English: a mention of the assignee, the Sigma workbook and page that were built, then one bullet per
     gap with the visual, the field (display name), the DAX measure, why it is missing, and what would solve it (for
     a semantic view: the metric name and expression to add; the owner adds it). End with "Posted by Claude on behalf
     of <user's name>."
  2. Show the exact text to the user and post it **only after they confirm**.
  3. Post with `addOrEditJiraIssueComment` (new comment) and `contentFormat: html`, writing the mention as
     `<span data-type="mention" data-user-id="<assignee accountId>">@<assignee displayName></span>` (the same HTML
     the Jira tools return for mentions). If the ticket has no assignee, don't mention anyone and say so.
  4. Re-read the comments (`listJiraIssueComments`, `responseContentFormat: html`) and check that the mention came
     out as a mention (`data-type="mention"`), not plain text. Give the user the comment link.
  - Never put secrets, connection ids or data values in the comment.

## Bundled files
- `README.md`: the user guide (prerequisites, install, how to use, security, settings, troubleshooting). Keep it in
  sync when a rule changes.
- `config.example.json`: the keys of `config.local.json` (written once per user, git-ignored). A private fork may add
  `config.team.json` with the team's defaults.
- `references/sv-change-log.md`: every semantic view change made through this skill.
- `scripts/sigma_cli.py`: cross-platform CLI with a hidden credential prompt, a host allow-list, a backup before
  each push, and page merging. It needs PyYAML only to read `.yaml`.
- `scripts/token_cache.py`: 1-hour reuse of the access token in the Windows Credential Manager (logon session only).
- `scripts/spec_merge.py`: the page merge used by the CLI (add or replace pages by name, keep the rest, refuse id
  collisions).
- `scripts/push_to_sigma.ps1`: a PowerShell fallback that replaces the whole workbook (single-page workbooks only).
- `scripts/sigma_schema_probe.py`: looks up exact keys and enums in Sigma's public OpenAPI.
- `references/sigma-spec-gotchas.md`: importer errors already hit and their fixes.
- `references/sql-patterns.md`: SEMANTIC_VIEW SQL patterns (additive bases, date roles, relative dates, ranks).
- `assets/example/`: a complete working example ("Activity" page; neutral placeholder names) with a generator script and SQL templates.
