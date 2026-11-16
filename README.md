# claude_skills

Claude Code skills. Each folder is one skill.

| Skill | What it does |
|---|---|
| [`sigma-yaml-from-semantic-views`](sigma-yaml-from-semantic-views/README.md) ([how to use](sigma-yaml-from-semantic-views/README.md#2-how-to-use-it)) | Rebuilds a Power BI report page (layout from the Jira ticket, data from the TMDL mapped to Snowflake Semantic Views) as a Sigma workbook page, and publishes it with each user's own Sigma API credentials. Runs on Claude Opus 5.5. |

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
saves them in `config.local.json` (git-ignored, never published). A team can keep a private fork with a
`config.team.json` of shared defaults.

## Updates

The skill pulls the latest version at the start of each run, and publishes what it learns back to this repository
(generic wording only: no company names, hosts, data or secrets).
