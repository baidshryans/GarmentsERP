# MCP Server Setup Guide — Jewel India ERP

This guide walks you through setting up the **Jewel India ERP MCP server** so an AI client (Claude Desktop, Claude Code, ChatGPT, etc.) can read live data from your ERP database via natural-language tool calls.

The server lives at [`backend/mcp_server.py`](../backend/mcp_server.py) and exposes **31 tools** — sales summaries, purchase reports, balance sheets, top customers, outstanding debtors/creditors, gold rates, scheme enrollments, and more.

---

## Table of Contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Two transport modes](#two-transport-modes)
4. [Setup A — Claude Code (this project)](#setup-a--claude-code-this-project)
5. [Setup B — Claude Desktop (local app)](#setup-b--claude-desktop-local-app)
6. [Setup C — Remote / claude.ai (SSE + tunnel)](#setup-c--remote--claudeai-sse--tunnel)
7. [Verifying the server works](#verifying-the-server-works)
8. [Critical gotchas](#critical-gotchas)
9. [Troubleshooting](#troubleshooting)
10. [Adding a new tool](#adding-a-new-tool)
11. [Available tools reference](#available-tools-reference)

---

## How it works

```
┌────────────────┐   stdio / SSE   ┌──────────────────┐   Django ORM   ┌──────────────┐
│  Claude client │ ───────────────▶│  mcp_server.py   │ ──────────────▶│ db.sqlite3   │
│ (Desktop / CC) │ ◀───────────────│  (FastMCP)       │ ◀──────────────│              │
└────────────────┘   tool calls    └──────────────────┘   results       └──────────────┘
```

- The MCP client (Claude Desktop / Claude Code) launches `mcp_server.py` as a subprocess.
- Communication happens over **stdio** (default) or **SSE** (for remote clients).
- Each `@mcp.tool()` function in `mcp_server.py` is exposed to the AI as a callable tool with auto-generated JSON schema (FastMCP introspects type hints).
- Tools run Django ORM queries against the same `db.sqlite3` your ERP uses, then return JSON.

**No API keys are needed.** The MCP server has no auth — security comes from running it locally over stdio.

---

## Prerequisites

- Python venv at `backend/env/` (already set up — uses Python 3.12 ARM64 on this machine).
- `mcp` package installed in that venv (already present — `backend/env/Scripts/mcp.exe`).
- A populated `db.sqlite3` at `backend/db.sqlite3`. An empty DB still works but tools return zeros / empty lists.

If the venv is missing, recreate with:

```bash
cd "D:\Jewel India ERP\backend"
python -m venv env
env\Scripts\pip.exe install -r requirements.txt
env\Scripts\pip.exe install mcp
```

---

## Two transport modes

| Mode | When to use | How clients connect |
|---|---|---|
| **stdio** (default) | Claude Desktop, Claude Code, any local desktop app | Client spawns the script as a child process |
| **SSE** | Remote / web clients like claude.ai | Server listens on an HTTP port; client connects to a URL |

For local AI work, **always use stdio** — it's faster, has no networking surface, and needs no tunnel.

---

## Setup A — Claude Code (this project)

The project already ships with [`.mcp.json`](../.mcp.json) at the repo root. When you open this folder in Claude Code, it auto-discovers and offers to start the server.

### The config file

```json
{
  "mcpServers": {
    "jewel-erp": {
      "command": "D:\\Jewel India ERP\\backend\\env\\Scripts\\python.exe",
      "args": ["D:\\Jewel India ERP\\backend\\mcp_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "jewel_test.settings",
        "DJANGO_ALLOW_ASYNC_UNSAFE": "true"
      }
    }
  }
}
```

### Steps

1. Open this directory in Claude Code.
2. On first launch you'll be prompted to approve the MCP server — click **Allow**.
3. Run `/mcp` (if your harness supports it) to confirm `jewel-erp` is connected, OR just ask: *"Use jewel-erp to get this month's sales summary."*

If you change `.mcp.json`, **end the session and start a fresh one** — the server is only spawned at session start.

---

## Setup B — Claude Desktop (local app)

Claude Desktop uses its own config file, separate from the one in this repo.

### 1. Locate the config file

| OS | Path |
|---|---|
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

On Windows, paste this into Run (`Win + R`):

```
%APPDATA%\Claude\claude_desktop_config.json
```

### 2. Add the `mcpServers` block

If the file already exists with other settings (e.g. a `preferences` block), **merge** — do NOT add a second top-level `{...}` object. The file must remain a single valid JSON object.

```json
{
  "mcpServers": {
    "jewel-erp": {
      "command": "D:\\Jewel India ERP\\backend\\env\\Scripts\\python.exe",
      "args": ["D:\\Jewel India ERP\\backend\\mcp_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "jewel_test.settings",
        "DJANGO_ALLOW_ASYNC_UNSAFE": "true"
      }
    }
  }
}
```

> ⚠️ Use **double backslashes** (`\\`) in JSON strings on Windows. Forward slashes also work: `"D:/Jewel India ERP/backend/..."`.

### 3. Validate the JSON

```bash
"D:\Jewel India ERP\backend\env\Scripts\python.exe" -c "import json; json.load(open(r'C:\Users\YOUR_USER\AppData\Roaming\Claude\claude_desktop_config.json')); print('VALID JSON')"
```

If this prints anything other than `VALID JSON`, fix the syntax before continuing — Claude Desktop silently ignores broken configs.

### 4. Fully quit and relaunch Claude Desktop

- Closing the window is **not enough** — it stays in the system tray.
- Right-click the tray icon → **Quit**, or use **File → Exit**.
- Then reopen.

### 5. Verify

In a new chat, click the **🔌 / tools icon** in the composer. You should see **jewel-erp** listed with 31 tools. Try:

> "Use jewel-erp to show me the sales summary for this month."

Approve permission the first time each tool runs.

---

## Setup C — Remote / claude.ai (SSE + tunnel)

Only do this if you specifically need the server reachable from claude.ai (the web app). For local testing, **prefer Setup A or B**.

### 1. Run the server in SSE mode

```bash
cd "D:\Jewel India ERP\backend"
set DJANGO_ALLOW_ASYNC_UNSAFE=true
env\Scripts\python.exe mcp_server.py --sse --port 8100
```

The server listens on `http://0.0.0.0:8100/sse`.

### 2. Expose with HTTPS (claude.ai requires it)

Pick one:

- **ngrok**: `ngrok http 8100` → copy the `https://xxxx.ngrok-free.app` URL.
- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8100`.

Your endpoint becomes `https://xxxx.ngrok-free.app/sse`.

### 3. Add as a Custom Connector

1. Open **claude.ai** → Settings → **Connectors** (requires Pro / Max / Team / Enterprise — not on free).
2. **Add custom connector**.
   - Name: `Jewel India ERP`
   - URL: `https://xxxx.ngrok-free.app/sse`
   - Auth: None
3. Save.

### ⚠️ Security warning

The MCP server has **zero authentication**. Anyone with the tunnel URL can read your entire ERP. Stop the tunnel when done, or put a reverse proxy with bearer-token auth in front of it.

---

## Verifying the server works

Run this smoke test from PowerShell or bash — it boots the server in-process and lists all registered tools without needing an MCP client:

```bash
cd "D:\Jewel India ERP\backend"
env\Scripts\python.exe -c "import os, sys; sys.path.insert(0, '.'); os.environ.setdefault('DJANGO_SETTINGS_MODULE','jewel_test.settings'); import django; django.setup(); import mcp_server; print('TOOLS:', len(mcp_server.mcp._tool_manager.list_tools()))"
```

Expected output:

```
TOOLS: 31
```

If you see a Python traceback, fix that before configuring any client — the same error will hit there too.

---

## Critical gotchas

These three issues will bite you every time. Memorize them.

### 1. `DJANGO_ALLOW_ASYNC_UNSAFE=true` is mandatory

FastMCP runs tool handlers inside an asyncio event loop. Django's ORM normally blocks sync queries from async contexts and raises:

```
You cannot call this from an async context - use a thread or sync_to_async.
```

The env var disables that guard. It's safe here because FastMCP serializes tool calls and we're not sharing connections across tasks.

**Long-term proper fix:** rewrite each tool body using `asgiref.sync.sync_to_async`. For now the env var is the pragmatic shortcut.

### 2. `claude_desktop_config.json` must be a single valid JSON object

If Claude Desktop already wrote a `preferences` block, do NOT append a second `{...}` underneath. Merge into one object with both keys:

```json
{
  "preferences": { ... },
  "mcpServers": { ... }
}
```

Two adjacent top-level objects = invalid JSON = Desktop silently ignores `mcpServers`.

### 3. Configs are read at client launch only

After editing `.mcp.json` or `claude_desktop_config.json`:

- **Claude Code:** end the current session, start a new one.
- **Claude Desktop:** quit fully (tray icon → Quit), then reopen.

Reloading the chat is not enough.

---

## Troubleshooting

### "MCP server `jewel-erp` failed to start"

Run the script manually to see the real error:

```bash
"D:\Jewel India ERP\backend\env\Scripts\python.exe" "D:\Jewel India ERP\backend\mcp_server.py"
```

It should sit silently waiting on stdin. If anything prints to stderr, that's the bug. Common causes:
- `ModuleNotFoundError: django` → wrong Python interpreter (not the one inside `backend/env/Scripts/`).
- `ImproperlyConfigured` → `DJANGO_SETTINGS_MODULE` env var missing or wrong.
- `No module named 'mcp'` → `pip install mcp` in the project venv.

### "You cannot call this from an async context"

The `DJANGO_ALLOW_ASYNC_UNSAFE=true` env var is missing from the `env` block. See [gotcha #1](#1-django_allow_async_unsafetrue-is-mandatory).

### "no such table: mastersconfig_retailmaster" (or any other table)

Django is reading the wrong database. The settings hard-code `BASE_DIR / 'db.sqlite3'` — confirm:

```bash
ls -la "D:\Jewel India ERP\backend\db.sqlite3"
```

If the file is 4 KB (empty), you need to seed it. If you have data in a differently named file, either rename it to `db.sqlite3` or edit `backend/jewel_test/settings.py` line 187 to point at the right path.

### Tools return zeros / empty lists

The server is working — your DB just has no data for that query/date range. Try a wider date range or load some test data.

### Claude Desktop shows no tools at all

1. Verify the config file is valid JSON (see [verification command](#3-validate-the-json)).
2. Confirm you fully quit and reopened (not just closed the window).
3. Check Claude Desktop logs:
   - Windows: `%APPDATA%\Claude\logs\`
   - macOS: `~/Library/Logs/Claude/`
4. Try the smoke test from [Verifying the server works](#verifying-the-server-works) to rule out a server-side bug.

### "MCP isn't available in this environment" when typing `/mcp`

`/mcp` is a Claude Code built-in slash command not enabled in every harness. The MCP tools themselves are still callable — just ask in natural language: *"Use jewel-erp to ..."*.

---

## Adding a new tool

Tools are plain Python functions decorated with `@mcp.tool()`. FastMCP introspects the signature and docstring to build the JSON schema the AI sees.

```python
@mcp.tool()
def get_my_thing(start_date: str, retail_code: str = "") -> str:
    """One-line description shown to the AI.

    Args:
        start_date: Date in YYYY-MM-DD format
        retail_code: Optional retail location code
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = MyModel.objects.filter(retail=retail, date__gte=start_date)
    return json.dumps({
        "count": qs.count(),
        "items": [{"id": x.id, "name": x.name} for x in qs[:20]],
    }, indent=2)
```

Rules:

1. **Always return a string** — JSON-encoded. The AI parses it back.
2. **Convert `Decimal` → `float`** with the existing `_decimal()` helper before serialising.
3. **Type-hint every argument** — FastMCP needs them to build the schema.
4. **Write a real docstring** — the AI uses it to decide when to call your tool.
5. **Keep tools sync** (`def`, not `async def`). FastMCP runs them in a thread.
6. **No state between calls** — each call is independent.

After adding a tool, restart the MCP client (see [gotcha #3](#3-configs-are-read-at-client-launch-only)).

---

## Available tools reference

All 31 tools live in [`backend/mcp_server.py`](../backend/mcp_server.py). Categorized:

### Sales
- `get_sales_summary(from_date, to_date, retail_code)` — totals, invoice count, top vendors
- `get_top_customers(from_date, to_date, limit, retail_code)`
- `get_customer_history(customer_name, retail_code)`
- `get_monthly_sales_trend(year, retail_code)`
- `compare_sales(period1_from, period1_to, period2_from, period2_to, retail_code)`

### Purchases
- `get_purchase_summary(from_date, to_date, retail_code)`
- `get_outstanding_creditors(as_of_date, retail_code)`
- `get_outstanding_debtors(as_of_date, retail_code)`

### Accounting
- `get_ledger_balance(ledger_name, retail_code)`
- `get_trial_balance_summary(from_date, to_date, retail_code)`
- `get_day_book(date, retail_code)`
- `search_ledgers(query, retail_code)`
- `get_cash_position(as_of_date, retail_code)`

### Financial reports
- `get_balance_sheet(as_of_date, retail_code)`
- `compare_balance_sheet(date1, date2, retail_code)`
- `compare_balance_sheet_by_fy(fy1_code, fy2_code, retail_code)`
- `get_profit_and_loss(from_date, to_date, retail_code)`
- `compare_profit_and_loss(p1_from, p1_to, p2_from, p2_to, retail_code)`
- `compare_pnl_by_fy(fy1_code, fy2_code, retail_code)`
- `list_financial_years(retail_code)`

### Inventory
- `get_stock_summary(retail_code)`
- `get_stock_valuation(as_of_date, retail_code)`
- `get_invoice_details(invoice_no, retail_code)`

### Manufacturing
- `get_karigar_jobs_status(retail_code)`

### Schemes (gold savings)
- `get_scheme_summary(retail_code)`
- `get_scheme_enrollments(status, retail_code)`
- `get_scheme_maturity_calendar(months_ahead, retail_code)`
- `get_scheme_overdue_payments(retail_code)`

### Other
- `get_gst_summary(from_date, to_date, retail_code)`
- `get_dashboard_summary(retail_code)`
- `get_gold_rates(date, retail_code)`

For exact signatures and return shapes, search `mcp_server.py` for the function name — every tool has a docstring describing its arguments.

---

## Quick reference card

```
SCRIPT     D:\Jewel India ERP\backend\mcp_server.py
PYTHON     D:\Jewel India ERP\backend\env\Scripts\python.exe
DB         D:\Jewel India ERP\backend\db.sqlite3
SETTINGS   jewel_test.settings
ENV VARS   DJANGO_SETTINGS_MODULE=jewel_test.settings
           DJANGO_ALLOW_ASYNC_UNSAFE=true   ← REQUIRED

CONFIGS    .mcp.json                                          (Claude Code, this repo)
           %APPDATA%\Claude\claude_desktop_config.json        (Claude Desktop, Windows)

SMOKE TEST cd backend && env\Scripts\python.exe -c "import os,sys; sys.path.insert(0,'.'); os.environ.setdefault('DJANGO_SETTINGS_MODULE','jewel_test.settings'); import django; django.setup(); import mcp_server; print(len(mcp_server.mcp._tool_manager.list_tools()), 'tools')"
```
