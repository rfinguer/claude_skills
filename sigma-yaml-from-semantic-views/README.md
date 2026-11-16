# Power BI page → Sigma (on Snowflake semantic views)

This Claude Code skill rebuilds **one Power BI report page** as **one page (tab) of a Sigma workbook**:

- the **layout** comes from the page's **Jira ticket** (description + every comment);
- the **data** comes only from the **Snowflake semantic views**, mapped from the DAX in the Power BI **TMDL**;
- Claude builds the page, publishes it to Sigma with **your own** Sigma API credentials, checks it, and tells you
  what could not be built (and, if needed, posts the gaps as a comment on the Jira ticket for the assignee).

You don't need to open a terminal: Claude runs everything, and Sigma sign-in / confirmation windows open on your
screen when needed.

---

## 1. Before you start (one time)

Claude checks all of this at the start of every run and gives you step-by-step instructions for anything missing.
It helps to have it ready:

| You need | Notes |
|---|---|
| **Company approval** (if required) | If your company requires an approval to use Claude Code with Snowflake, get it before the first run. |
| **Claude Code** (desktop app or CLI) on **Opus 5.5** | The skill must run on **Claude Opus 5.5** (`claude-opus-5-5`) to keep the quality. Pick it in the app's model selector, or `/model` in the CLI. Claude stops and asks you to switch if another model is selected. |
| **Python 3.10+** (with tkinter) and **Git** | Windows: when installing Python, tick "Add python.exe to PATH". |
| **Snowflake CLI** with your own connection to your Snowflake account | `python -m pip install --user snowflake-cli`, then `snow connection add` (authenticator `externalbrowser`, your own login). |
| **A Snowflake role** that can read the semantic views (`snowflake_role` in your settings), granted to your user | Requested from the Snowflake administrator. Never use someone else's login. |
| **Your own Sigma API client** (Client ID + Secret) | Sigma → Administration → **Developer Access** → **Create New** → API client, owner = you, permission to create/edit workbooks. Copy the Secret when it is shown (only once). If you can't see Developer Access, ask a Sigma admin. |
| **Edit access to the target Sigma workbook** | The workbook must already exist (create and save it once in Sigma, e.g. "<your name> - test"). You pick it from a list when publishing. |
| **The Power BI TMDL file** of the report | Required (it holds the DAX). Export it from Power BI or ask the report owner. |
| **Jira access** | Claude connects the Atlassian MCP for you; you only sign in with your own Atlassian account. |

### Install

Windows (PowerShell):

```powershell
git clone https://github.com/rfinguer/claude_skills.git "$HOME\.claude\claude_skills"
New-Item -ItemType Junction -Path "$HOME\.claude\skills\sigma-yaml-from-semantic-views" -Target "$HOME\.claude\claude_skills\sigma-yaml-from-semantic-views"
```

macOS / Linux:

```bash
git clone https://github.com/rfinguer/claude_skills.git ~/.claude/claude_skills
ln -s ~/.claude/claude_skills/sigma-yaml-from-semantic-views ~/.claude/skills/sigma-yaml-from-semantic-views
```

Restart Claude Code after installing. The skill updates itself (`git pull`) at the start of each run.

---

## 2. How to use it

1. Open Claude Code in a working folder of your choice (Claude saves the generated files there), with **Opus 5.5**
   selected as the model.
2. Type **`/sigma-yaml-from-semantic-views`** (you can add the ticket: `/sigma-yaml-from-semantic-views PROJ-123`).
3. Claude runs the preflight checks and fixes or explains anything missing. **Snowflake sign-in:** when Claude first
   talks to Snowflake (and whenever your login expired), your **web browser opens your company's / Snowflake sign-in page**.
   Sign in with your company account (approve MFA if asked) and come back: Claude waits and continues on its own. What passed is remembered in
   `preflight.local.json`, so later runs skip it.
4. Answer the questions: the **Jira ticket** key or URL (if you didn't give it) and the **path of the TMDL file**.
   You pick the Sigma workbook later, in a searchable window.
5. Claude reads the ticket, maps the DAX to the semantic views, writes and tests the SQL in Snowflake, and builds the
   Sigma page. It tells you what it found along the way.
6. **Sigma windows** open on your screen:
   - **Sign in**: type your own Client ID and Secret (masked). Skipped for 1 hour after a successful sign-in.
   - **Connection** (only when needed) and **Workbook** (always): pick from a searchable list.
   - **Confirm**: shows the pages that will be kept / added / replaced and a red warning. Click **Publish**.
7. Claude checks the published page through the API and gives you a report: what was built, what is empty and why.
8. If something from the ticket could not be built, Claude shows you a **Jira comment** (mentioning the ticket
   assignee) and posts it **only after you confirm**.
9. Open the workbook in Sigma (reload it) and check every section.

### Good to know

- **Every push publishes immediately.** Sigma's API has no "save as draft". If you have a **Draft** open in the Sigma
  editor, it is now outdated: **discard it** (publishing it would bring back the old version).
- **Only your page changes.** The workbook's other pages are kept. Re-running the skill for the same page replaces
  only that page (matched by name). A backup of the workbook is saved before every push (`backup_<id>_<time>.json`).
- **Bookmark navigators** become a segmented control when the views are the same visual, or the views are stacked on
  the page (each under a title) when they are different visuals. Tabbed containers are never used.
- **The page shows only what the semantic views support.** Anything else stays empty and is listed in the report and
  in the Jira comment. If your Snowflake role owns the semantic views, Claude can add a missing public metric (only
  additions, after your OK, with a backup and a check that nothing else changed); otherwise the gap goes to the
  Jira comment.
- **Some Power BI features have no Sigma equivalent** (e.g. a color scale based on a different column). Claude uses
  the closest option and lists the difference.

---

## 3. Security

- Use **your own** Sigma API client, Snowflake login and Atlassian account. Never share them.
- **Never paste the Sigma Client ID/Secret in the chat**, a file, or a command. Type them only in the Sigma sign-in
  window. If a secret ever shows up in plain text, rotate it in Sigma.
- After sign-in, only the short-lived Sigma **access token** is kept for up to 1 hour, in the Windows Credential
  Manager, for your Windows session. To forget it now, ask Claude to "log out of Sigma".
- Credentials are only sent over HTTPS to `*.sigmacomputing.com`.
- Claude only reads Jira, except for the gap comment you approve.

---

## 4. Your settings (`config.local.json`)

On the first run the skill asks for your settings once (or copies a team `config.team.json` if your fork has one) and saves them in `config.local.json` (next to `SKILL.md`, never published).
Ask Claude to change a setting at any time ("change the skill's Snowflake role to ...").

| Key | Meaning |
|---|---|
| `sv_database`, `sv_schema` | Where the semantic views are. |
| `skip_sv_prefix` | Semantic views to ignore (test copies), e.g. `ZZ_`. |
| `snowflake_account`, `snowflake_role` | Your Snow CLI connection's account, and the role Claude uses. |
| `jira_site` | The Jira site (`<site>.atlassian.net`). |
| `sigma_api_host` | Your Sigma organization's API host. |
| `language` (optional) | The language Claude uses with you (default English). |

---

## 5. Troubleshooting

| What you see | What to do |
|---|---|
| "Repository not found" when the skill updates | The clone points to a repository you can't access (e.g. a private fork): check `git remote -v` and your access. |
| The Sigma window doesn't appear | It opens on top of other windows; check the taskbar. Closing it cancels the push. |
| Sigma sign-in fails (HTTP 400/401) | Wrong Client ID/Secret, or the wrong `sigma_api_host` for your organization. |
| Push fails with **403 Permission denied** | You don't have **Can edit** on that workbook. Ask its owner. |
| Push fails with **400** and a list of errors | Sigma rejected the spec (nothing was changed). Claude fixes it and pushes again. |
| The page shows old errors in Sigma | You have an outdated **Draft** open: discard it and reload. |
| Claude seems stuck on a Snowflake step | A browser window is waiting for your Snowflake sign-in (it may be behind other windows). Complete it. |
| Snowflake says the role isn't granted | Ask the Snowflake administrator to grant `snowflake_role` to your user. |
| A column is empty | Usually a field the semantic views can't support, or test data that doesn't join. It is listed in Claude's report. |
| Jira can't be read | Claude starts the Atlassian sign-in; after signing in, start a new Claude Code session and run the skill again. |

---

## 6. Running the Sigma CLI yourself (optional)

Claude normally runs it for you. In a terminal (sign-in prompts are hidden):

```bash
python scripts/sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com workbooks
python scripts/sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com pages --workbook-id <uuid>
python scripts/sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com push --workbook-id <uuid> --yaml <report>.json --dry-run
python scripts/sigma_cli.py --base-url https://api.us.azure.sigmacomputing.com logout
```

`--dry-run` shows what would change without publishing. To restore a backup:
`push --replace-workbook --yaml backup_<id>_<time>.json`.

---

## 7. Help and improvements

The skill improves itself: when it learns something (a fix, a new pattern, a rule you ask for), it updates this
repository. Questions or access requests: the repository owner.
