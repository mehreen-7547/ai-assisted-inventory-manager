# AI Inventory & Demand Intelligence System

A local Django application for a small business to manage products, suppliers, stock, sales and purchase orders, with AI-assisted demand forecasting and inventory decision support. Built as a Techmindz academic full-stack project.

## Implemented features

- **Accounts and roles:** Admin, Inventory Manager and Sales Staff; login/logout, password changes and recovery, employee management.
- **Catalog:** supplier and product registration, editing, active/inactive status, product stock history.
- **Inventory and sales:** stock adjustments, sales recording and details, sale voiding, stock movement history.
- **Purchasing:** purchase order creation, listing, detail and status workflow; goods receipt against an order.
- **Dashboards:** role-specific homepages, stock alerts, sales summaries and Manager's prioritized “Needs attention today” panel.
- **Demand intelligence:** historical daily sales, Chronos-Bolt Tiny forecasts, historical forecast evaluation, stock-shortage estimates, reorder suggestions and unusual-sales detection.
- **Forecast comparison:** Manager-only eight-completed-week comparison of AI forecasts against the previous seven-day average and predict-zero baselines, showing absolute errors and skipped product-weeks.

AI predictions are decision support, not guaranteed future sales. The historical comparison can show that a simple baseline outperforms AI.

## Technology

Python, Django 6.0.9, SQLite, Django templates, local CPU-based PyTorch and Chronos forecasting. The project does not require a paid forecasting API. Model weights and Python dependencies may require an initial internet download.

## Local setup (Windows PowerShell)

Use Python 3.12 as described in [Module 0 setup notes](README_M0.md). From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
notepad .env
```

Replace `DJANGO_SECRET_KEY=replace-with-random-secret` with the generated secret. Keep `DB_ENGINE=sqlite` and `DB_NAME=db.sqlite3` for local development. Never commit `.env`.

For AI features, install the CPU PyTorch wheel followed by the pinned forecasting dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

Then prepare and run Django:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/login/ and sign in with a user created for the relevant role. A fresh database has no sample business data or login accounts by default; prepare users and demo records before presenting.

## Main pages

| Page | Route |
| --- | --- |
| Role-specific dashboard | `/` |
| Login | `/login/` |
| Employees | `/employees/` |
| Suppliers | `/suppliers/` |
| Products | `/products/` |
| Sales | `/sales/` |
| Purchase orders | `/purchase-orders/` |
| Demand intelligence | `/intelligence/` |
| Historical forecast comparison | `/intelligence/evaluation/` |

Access depends on the logged-in user's role. The comparison page is restricted to Managers.

## Forecast evaluation methodology

For each product and each of eight completed weeks, the evaluator obtains the preceding 60 days of history and the following seven actual days. It forecasts from the cutoff **before** the evaluation week, checks prediction dates and nonnegative finite values, and compares three weekly totals:

1. AI: sum of seven Chronos median (`p50`) daily predictions.
2. Previous seven-day average: the total sold during the previous seven days.
3. Zero baseline: a prediction of zero.

Absolute error is `abs(actual weekly sales - predicted weekly sales)`. The dashboard reports mean weekly absolute error across valid product-weeks, with skipped periods counted separately. A POST explicitly recalculates; results are cached for 24 hours.

In one reported local demonstration (48 products), 336 product-weeks were evaluated and 48 skipped. Mean errors were AI 3.45, previous-week baseline 3.29 and zero 4.30. These are example results, not fixed benchmarks.

## Testing and scope

The source at commit [78278d5](https://github.com/mehreen-7547/ai-assisted-inventory-manager/commit/78278d5) was reported to pass 528 Django tests, with a clean system check and no pending migrations. Re-run tests on your own environment before submission.

The project is intended for local academic demonstration, not production deployment. SQLite and local model inference have practical concurrency and performance limits. The promised UI refinement and final submission review are separate remaining phases.

## Further reading

- [Module 0 setup and AI feasibility](README_M0.md)
- [Five-minute demonstration guide](DEMO_SCRIPT.md)
