# Garment Manufacturing ERP

Django 5 + DRF, SQLite for now (database-neutral code). Build brief: `CLAUDE.md`; requirements: `docs/`.

## Run locally (Windows)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in; the first-install setup wizard opens automatically.
`manage.py seed_defaults` re-runs every seeder (safe to repeat).

## Tests

```bash
.venv/Scripts/python -m pytest
```

After every test the autouse fixture in `tests/conftest.py` checks that all vouchers balance and the trial balance tallies.

## Where things are

- `core/services/` numbering (counter table), period locks, factories, setup
- `ledger/services/posting.py` the only way vouchers are created; `opening.py` opening balances
- `core/scoping.py` factory scoping + screen permissions (enforced server-side)
- `static/css/tokens.css` all design tokens (light + dark); no raw hex elsewhere
