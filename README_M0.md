# Module 0 — Django + SQLite + AI feasibility (Windows PowerShell)

Status: Local Django verification completed (5/5 tests passed). Both Chronos-Bolt Tiny and Chronos-2 successfully generated forecasts on CPU. Chronos-Bolt Tiny is the recommended default due to lower memory usage. Final Module 0 documentation and security checks are pending.

## Agreed database and stock rule

- SQLite for now, configured entirely from `.env`. MySQL can be selected later by changing environment values and installing its driver **after your approval**.
- For a sale, the future stock service will run a **single atomic conditional update** inside `transaction.atomic()`: update only when `on_hand >= quantity`. If zero rows are updated, refuse the sale. The same transaction will create the sale and stock-movement records.
- Module 0 contains a **test-only product table** (created and deleted during tests) to verify the mechanism. Real stock services and sale tests come in Modules 3 and 4.
- SQLite can report `database is locked` under heavy simultaneous writes. The Module 0 test proves two sequential sale attempts cannot consume the same last unit; it does **not** prove performance or successful processing of simultaneous requests.

## 1. Verify Python (64-bit Python 3.12 or 3.13)

Open PowerShell in this extracted folder:

```powershell
py -3.12 --version
```

If you have 3.13 instead, use `py -3.13` in the next command.

## 2. Create a virtual environment and install Django

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m django --version
```

Expected Django version: `6.0.9` (the starter's pinned version). If installation fails, share the error rather than changing versions without discussion.

## 3. Configure `.env`

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
notepad .env
```

Replace `DJANGO_SECRET_KEY=replace-with-random-secret` with the generated key. Leave `DB_ENGINE=sqlite` and `DB_NAME=db.sqlite3` unchanged. Keep `.env` private.

The settings file reads `DB_ENGINE`, `DB_NAME`, and (for a later MySQL switch) `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` from `.env`. MySQL requires its own server and Python driver, which are **not** installed now.

## 4. Create the database and run Django tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test -v 2
.\.venv\Scripts\python.exe manage.py runserver
```

Expected:
- `System check identified no issues`.
- `db.sqlite3` created after `migrate`.
- `Ran 5 tests` and `OK`, including **second sale of last unit refused** and **rollback restores stock**.
- Visit http://127.0.0.1:8000/ and see `Module 0 setup is running`.

Press `Ctrl+C` to stop the server.

## 5. Install AI dependencies (free, CPU)

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
.\.venv\Scripts\python.exe -c "import torch, chronos, psutil; print('Torch:', torch.__version__)"
```

The first install/download may be large. No paid service, account, model training or API key is required for the public weights. An internet connection is needed initially. If a pinned package is unavailable for your Python version, report the error before changing the dependency.

## 6. Run ONE script to test BOTH models

```powershell
.\.venv\Scripts\python.exe scripts\ai_probe.py
```

The script separately tests **Chronos-Bolt Tiny** and **Chronos-2**. Each prints:
- `WORKED: YES` or `WORKED: NO`
- `SECONDS TAKEN`
- `PEAK MEMORY` in MB (peak process RAM, not total laptop RAM)
- On success, `FORECAST ONLY` time and first forecast values

Results are saved to `ai_probe_results.json` (ignored by Git). Models run one at a time in independent processes to measure each one's memory use. First run includes model download time. Re-run after download to measure normal load/forecast time.

If your laptop has limited RAM, start with `--model bolt` and send the result before running the default both-model test:

```powershell
.\.venv\Scripts\python.exe scripts\ai_probe.py --model bolt
```

If Chronos-2 fails, report the error. That does not invalidate a successful Bolt test.

## 7. Git repository

This project is already initialized as a Git repository
and connected to GitHub.

Do not run `git init` again.

Before committing, verify that `.env`, `db.sqlite3`,
and other sensitive files remain excluded from Git.

## Module 0 acceptance checks

1. PASS — Django 6.0.9 starts successfully with SQLite configured through `.env`.
2. PASS — All five Django tests passed, including last-unit refusal and transaction rollback.
3. PASS — Chronos-Bolt Tiny and Chronos-2 both generated valid 30-day forecasts locally on CPU.
4. PASS — Chronos-Bolt Tiny selected as the default model. It used 363.5 MB peak process memory versus 811.8 MB for Chronos-2. Forecast accuracy evaluation is deferred to Module 8.
5. PASS — Module 0 verification, documentation, and basic security checks completed. PENDING — Create the `m0-complete` tag and obtain architecture and permissions approval before Module 1.

**Future stock rule:** In Modules 3–5, stock-changing service functions must update stock and write a matching `StockMovement` in the **same** database transaction. Module 0's test is not a substitute for the full sales and ledger tests.
