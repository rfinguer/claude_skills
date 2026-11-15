# claude_skills

Claude Code skills. Each folder is one skill.

| Skill | What it does |
|---|---|
| [`sigma-yaml-from-semantic-views`](sigma-yaml-from-semantic-views/SKILL.md) | Rebuilds a Power BI report page (from a Jira ticket + TMDL) as a Sigma workbook page on Snowflake Semantic Views, and publishes it with each user's own Sigma API credentials. |

## Install (once)

Clone the repository and link the skill into your Claude skills folder, so `git pull` keeps it current.

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

Then start the skill (`/sigma-yaml-from-semantic-views`). On the first run it asks for your company settings once and
saves them in `config.local.json` (git-ignored, never published).

## Updates

The skill pulls the latest version at the start of each run, and publishes what it learns back to this repository
(generic wording only: no company names, hosts, data or secrets).
