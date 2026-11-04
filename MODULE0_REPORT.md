# Module 0 report — pending laptop verification

## a) Built (five lines)
1. Django starter retained with SQLite chosen from `.env`.
2. Optional MySQL configuration can be enabled later without editing settings code.
3. Temporary test-only stock table checks atomic conditional updates.
4. One script tests both pretrained forecasting models independently on CPU.
5. Results show worked/not worked, elapsed seconds and peak process RAM.

## b) Files created/changed
- Changed: `config/settings.py`, `.env.example`, `core/tests.py`, `scripts/ai_probe.py`, `README_M0.md`.
- Added: `SQLITE_ARCHITECTURE_AMENDMENT.md`, `MODULE0_REPORT.md`.
- Unchanged: requirements files, existing views/templates/URL routes, `.gitignore`.

## c) Commands
See `README_M0.md` steps 1–6. Main checks: `python manage.py check`, `python manage.py migrate`, `python manage.py test -v 2`, `python manage.py runserver`, `python scripts/ai_probe.py` (use the `.venv` Python paths in the README).

## d) Manual checks / expected results
1. Django homepage opens: `Module 0 setup is running`.
2. `manage.py test -v 2` reports 5 tests and OK.
3. AI script reports one result per model; successful forecasts have 30 days and finite values.
4. `ai_probe_results.json` contains time and memory for each model.

## e) Automated tests / failure conditions
- Home page: fails on missing route/template or incorrect response.
- Timezone: fails if not Asia/Kolkata or timezone support disabled.
- SQLite connection: fails if another DB backend is active (this Module 0 test intentionally expects SQLite).
- Last unit: fails if second deduction succeeds or stock becomes negative.
- Rollback: fails if a simulated failure leaves stock deducted.

## f) Assumptions and limits
- Python 3.12/3.13 and Django 6.0.9 pinned; actual installation on the user's laptop pending.
- AI weights and laptop resource use unverified until the user runs the script.
- No production Product/Sale/StockMovement model added yet.
- SQLite sequential tests do not prove behavior under simultaneous write requests.
- No agreed feature or role changes made.

## g) Suggested Git commit message
`M0: SQLite env config and atomic stock proof; AI feasibility`

## h) Interview questions (one-line answers)
1. **How do you prevent a sale from reducing stock below zero?** A conditional database update changes stock only when the available quantity is sufficient.
2. **What if saving the sale fails after the deduction?** The transaction rolls back, restoring the previous quantity.
3. **What did you verify about AI?** The local probe measures whether each pretrained model produces a valid forecast, and records time and memory; laptop results are still pending.

## Learn this
- A **virtual environment** isolates Python packages for this project.
- `.env` keeps local configuration separate from committed source code.
- **SQLite** stores data in a local database file.
- `transaction.atomic()` groups operations so failures can roll them back.
- An **atomic conditional update** checks stock and deducts it in one database statement.

**Three Django concepts:** settings (`config/settings.py`), test cases (`core/tests.py`), and ORM `filter().update()` (database operations through Python).
