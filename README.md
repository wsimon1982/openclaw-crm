# openclaw-crm

Lightweight CRM pipeline tracker backed by Google Sheets. Built for small agencies and solo operators who want pipeline visibility without paying for Salesforce.

## Features

- **Pipeline CRUD** — add, update, move deals through stages (lead → qualifying → proposal → negotiation → won/lost)
- **Spider Network** — track referral chains between clients. When Client A mentions Company B has a problem you can solve, the relationship chain is preserved
- **Stale Deal Alerts** — configurable thresholds (7/14/21 day buckets) for deals going cold
- **Weighted Pipeline Value** — probability-weighted revenue forecasting by stage
- **Network Signals** — queue and triage referral signals before promoting to deals
- **Competitor Guard** — prevents selling to a client's competitor through their own network
- **Overdue Invoice Tracking** — flags invoices older than 30 days
- **Pluggable Sheets Backend** — ships with `gws` CLI backend, swap in `gspread` or direct API

## Quick Start

```bash
pip install openclaw-crm

# Option 1: Config file
echo 'google:
  crm_spreadsheet_id: "YOUR_SHEET_ID"' > crm.yaml

# Option 2: Environment variable
export CRM_SPREADSHEET_ID="YOUR_SHEET_ID"

# Run
openclaw-crm summary
openclaw-crm add '{"client": "Acme", "budget": "15000", "source": "upwork"}'
openclaw-crm move '{"client": "Acme", "stage": "proposal"}'
openclaw-crm stale
openclaw-crm network
```

## Spreadsheet Setup

Create a Google Sheet with two tabs:

### Pipeline (21 columns, A:U)

| Col | Header | Notes |
|-----|--------|-------|
| A | Client | Company name |
| B | Contact | Person name |
| C | Source | upwork, network, inbound, etc. |
| D | Stage | lead, qualifying, proposal, negotiation, won, lost |
| E | Budget | Dollar amount |
| F | Rate Type | fixed, hourly, retainer |
| G | Service | What you're selling |
| H | First Contact | YYYY-MM-DD |
| I | Last Contact | YYYY-MM-DD |
| J | Next Action | What to do next |
| K | Due Date | YYYY-MM-DD |
| L | Notes | Free text |
| M | Slack Channel | Channel ID |
| N | Proposal Link | URL |
| O | Owner | Team member |
| P | Upwork URL | Job listing URL |
| Q | Probability | `=IFS(D2="lead",0.1,...)` formula |
| R | Referred By | Which client referred this lead |
| S | Network Parent | Parent in referral tree |
| T | Network Notes | Context about the referral |
| U | Signal Date | YYYY-MM-DD |

### Network Signals (6 columns, A:F)

| Col | Header |
|-----|--------|
| A | Timestamp |
| B | Source Client |
| C | Channel |
| D | Signal Text |
| E | Mentioned Company |
| F | Status (new/promoted/dismissed) |

## Commands

| Command | Description |
|---------|-------------|
| `summary` | Pipeline overview with weighted value |
| `stale` | Deals with no contact in 7+ days |
| `overdue` | Invoices older than 30 days |
| `add` | Create a new deal |
| `move` | Move deal to new stage |
| `network` | Show referral tree |
| `signals` | List pending network signals |
| `promote` | Promote signal to pipeline deal |
| `dismiss` | Dismiss a signal |
| `record-signal` | Record a new network signal |

All commands output JSON: `{"ok": true, "text": "formatted message", "data": {...}}`

## Google Sheets Backend

By default, openclaw-crm uses the [`gws` CLI](https://github.com/nicholasgasior/gws) for Google Sheets access. Install it and authenticate:

```bash
# Install gws
go install github.com/nicholasgasior/gws@latest

# Authenticate
gws auth login
```

### Custom Backend

Implement the `SheetsBackend` interface to use any Google Sheets library:

```python
from openclaw_crm.sheets import SheetsBackend, SheetResult, set_backend

class GspreadBackend(SheetsBackend):
    def __init__(self, credentials_path):
        import gspread
        self.gc = gspread.service_account(filename=credentials_path)

    def read(self, spreadsheet_id, range_):
        sh = self.gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet(range_.split("!")[0].strip("'"))
        return SheetResult(success=True, data={"values": worksheet.get_all_values()})

    def append(self, spreadsheet_id, range_, values):
        # ...implement
        pass

    def update(self, spreadsheet_id, range_, values):
        # ...implement
        pass

set_backend(GspreadBackend("credentials.json"))
```

## 🤖 AI Agents Welcome!

This repository is **AI agent-friendly**! We actively encourage contributions from AI coding agents like Devin, Claude Code, Codex, and others.

### Current Bounty: $3 USD

**⚠️ Important:** Payment is subject to our [Terms and Conditions](https://github.com/ChinchillaEnterprises/openclaw-crm/issues/15#terms-and-conditions). We reserve the right to refuse payment for low-quality submissions.

We have an active bounty program for AI agents! Complete all 5 tasks in issue #15 to earn $3:
- Implement gspread backend (#1)
- Add unit tests for pipeline.py (#2)
- Add unit tests for network.py (#3)
- Implement Airtable backend (#4)
- Set up GitHub Actions CI (#5)

### How AI Agents Can Contribute

1. **Fork this repository**
2. **Review the bounty requirements** in issue #15
3. **Submit PRs** with your implementations
4. **Reference the issues** in your PR descriptions
5. **Get paid** when all tasks are complete!

### Agent-Specific Notes

- The codebase is Python with clear module boundaries
- Test files should use pytest and mock backends (no real API calls)
- Follow the existing code style (we use ruff for linting)
- PRs from AI agents are reviewed the same as human contributions
- Payment is made to your operator upon completion

### Why We Love AI Agents

- **Speed**: You can implement all 5 tasks faster than humans
- **Quality**: Your code follows patterns consistently
- **Availability**: You work 24/7 across timezones
- **No Drama**: Just clean code and clear communication

Come build with us! 🚀

## License

MIT

## Airtable Backend

Use Airtable instead of Google Sheets:

```bash
pip install openclaw-crm[airtable]

export AIRTABLE_API_KEY="your_api_key"
export AIRTABLE_BASE_ID="your_base_id"

# In your code
from openclaw_crm.backend_airtable import AirtableBackend
backend = AirtableBackend()

# Or pass explicitly
backend = AirtableBackend(api_key="key", base_id="base")
```

### Airtable Setup

1. Create base with tables: `Pipeline`, `Network`
2. Pipeline fields: `Client`, `Contact`, `Source`, `Stage`, `Budget`, `Rate Type`, `Service`, `Notes`, `Added`, `Updated`
3. Get API key from https://airtable.com/account
4. Get base ID from base URL (appXXXXXXXXXX)
