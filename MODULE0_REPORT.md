# Module 0 Report — Django, SQLite and AI Feasibility

**Status:** Module 0 implementation, local verification, documentation, and basic Git security checks completed. Completion tag pending. Architecture and permissions approval required before Module 1.

## a) Built (five lines)

1. Configured Django 6.0.9 with SQLite using environment variables.
2. Retained optional MySQL configuration for a future approved migration.
3. Verified conditional stock deduction and transaction rollback using temporary test models.
4. Tested Chronos-Bolt Tiny and Chronos-2 locally using pretrained weights on CPU.
5. Selected **Chronos-Bolt Tiny as the default forecasting model** based on lower memory usage.

## b) Files created/changed

- `config/settings.py` — environment-based database configuration and application settings.
- `.env.example` — safe configuration template.
- `core/tests.py` — five automated tests.
- `scripts/ai_probe.py` — CPU forecasting feasibility test.
- `requirements.txt` — pinned core dependencies.
- `requirements-ai.txt` — pinned AI dependencies.
- `README_M0.md` — installation and execution instructions.
- `SQLITE_ARCHITECTURE_AMENDMENT.md` — database and stock-update decisions.
- `MODULE0_REPORT.md` — verification results and conclusions.

No production inventory or sales models have been implemented.

## c) Commands executed

```powershell
python -m pip install -r .\techmindz_inventory_module0_sqlite_atomic\requirements.txt
python .\techmindz_inventory_module0_sqlite_atomic\manage.py migrate
python .\techmindz_inventory_module0_sqlite_atomic\manage.py test core
python .\techmindz_inventory_module0_sqlite_atomic\manage.py runserver

python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r .\techmindz_inventory_module0_sqlite_atomic\requirements-ai.txt

python .\techmindz_inventory_module0_sqlite_atomic\scripts\ai_probe.py --model bolt
python .\techmindz_inventory_module0_sqlite_atomic\scripts\ai_probe.py
```

Commands were executed from the parent project directory with the virtual environment activated.

## d) Manual checks and actual results

**Development environment**

- Python 3.12.12
- Django 6.0.9
- SQLite database initialized successfully.
- All 18 initial Django migrations applied.
- Development server and homepage worked.
- Django admin login verified.
- `.env` and `db.sqlite3` confirmed ignored and untracked.

**AI feasibility — both-model run**

| Measurement | Chronos-Bolt Tiny | Chronos-2 |
|---|---|---|
| Status | PASS | PASS |
| Total execution | 7.30 seconds | 59.74 seconds |
| Peak process memory | 363.5 MB | 811.8 MB |
| Forecast computation | 0.01 seconds | 0.05 seconds |
| First-day P10 | 7.37 | 8.85 |
| First-day P50 | 8.42 | 9.03 |
| First-day P90 | 9.39 | 9.15 |

Both models received the same 90-day synthetic sales history and generated 30-day forecasts.

Chronos-2's execution time included its initial model download. Total execution times are therefore not directly comparable.

**Model recommendation:** Chronos-Bolt Tiny is the default because it completed the test successfully while using substantially less memory. Chronos-2 remains an alternative for later evaluation.

## e) Automated tests and failure conditions

**Result: 5 tests passed, 0 failures.**

1. Homepage test — verifies successful response and expected content.
2. Timezone test — verifies `Asia/Kolkata` and `USE_TZ = True`.
3. SQLite test — verifies the configured database connection.
4. Last-unit stock test — verifies that a second sequential deduction is refused.
5. Transaction rollback test — verifies that stock is restored after a simulated failure.

The stock tests use temporary models and tables, not production inventory models.

## f) Assumptions, decisions and limitations

**Confirmed decisions**

- Python 3.12 and Django 6.0.9.
- SQLite for local development instead of MySQL.
- Database settings read from `.env`, allowing a later approved MySQL migration.
- Chronos-Bolt Tiny as the default forecasting model.
- Separate core and AI dependency files.
- CPU-only forecasting without model training or paid APIs.

**Limitations**

- SQLite sequential tests do not prove safety or throughput under simultaneous requests. Concurrent writes may encounter database-lock errors.
- Actual Product, Sale and StockMovement models and services remain unimplemented.
- Forecast accuracy has not been established.
- Formal backtesting, baseline comparison and P10–P90 interval coverage are deferred to Module 8.
- AI dependencies are used by the standalone forecasting script, not required for the current Django application's startup.
- Real inventory tests must be introduced when production models and stock services are implemented.
- Final Git history security verification remains pending.

## g) Suggested Git commit message

`docs: finalize Module 0 verification and model recommendation`

After completing all mandatory checks, tag the verified commit:

`m0-complete`

## h) Interview questions

**1. How do you prevent stock from becoming negative?**

Use an atomic conditional database update inside a transaction. The deduction succeeds only when sufficient stock exists.

**2. What happens if a sale fails after stock is deducted?**

The database transaction rolls back, restoring the original stock quantity.

**3. Why did you select Chronos-Bolt Tiny?**

Both pretrained models worked locally, but Chronos-Bolt Tiny used substantially less memory. Forecast accuracy will be evaluated later before any final production decision.

## Learn this

- **Virtual environment:** Isolates project-specific Python packages.
- **`.env`:** Stores local configuration separately from source code.
- **SQLite:** Provides a file-based relational database.
- **`transaction.atomic()`:** Ensures grouped database operations commit or roll back together.
- **Conditional update:** Changes stock only when a database-level condition is satisfied.
- **Forecast quantiles:** P10, P50 and P90 represent different points in a predictive distribution, not guaranteed minimum and maximum sales.

**Three Django concepts:** Settings configuration, automated test cases, and ORM conditional updates.