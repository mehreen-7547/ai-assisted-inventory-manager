# Five-minute academic demonstration — AI Inventory & Demand Intelligence

**Preparation:** Start the local Django server, sign in as an Inventory Manager, and make sure the database already contains suitable products, suppliers, sales history and purchase orders. Keep an Admin account available if demonstrating account management. Forecast comparison may require local model loading; run it before the timed presentation if the environment is slow. Do not present precomputed results as a new live run.

| Time | Screen | Demonstration and explanation |
| --- | --- | --- |
| 0:00–0:35 | Login and Manager dashboard (`/`) | Explain the business problem: keeping enough stock without over-ordering. Point out Manager summary and “Needs attention today” ranking. |
| 0:35–1:15 | Products (`/products/`) and suppliers (`/suppliers/`) | Show a product, supplier relationship, available stock and stock history. Mention product and supplier status management. |
| 1:15–2:00 | Sales (`/sales/`) | Show a recorded sale and its detail. Explain that sales change inventory through validated stock operations; avoid altering demo data unless prepared. |
| 2:00–2:45 | Purchase orders (`/purchase-orders/`) | Open an existing purchase order, show its status and receipt workflow. Explain incoming stock and the distinction between ordering and receiving. |
| 2:45–3:45 | Demand intelligence (`/intelligence/`) | Select a prepared product and explain forecast, shortage warning, reorder recommendation and unusual sales patterns. Predictions help the Manager decide, but do not automatically place orders. |
| 3:45–4:35 | Forecast comparison (`/intelligence/evaluation/`) | Explain the eight completed weeks and three methods. Show evaluated/skipped counts, mean absolute errors and the best method. In the recorded sample, previous-week baseline 3.29 beat AI 3.45 and zero 4.30; use actual screen values if they differ. |
| 4:35–5:00 | Return to dashboard | Summarize: operational records feed sales history, history supports AI analysis, and the Manager remains responsible for purchasing decisions. |

## Key explanations for questions

**Why Django?** It provides authentication, forms, ORM-backed database access, routing and templates for the complete application.

**Where is AI used?** Chronos-Bolt Tiny produces historical-data-based demand forecasts. Shortage and reorder services consume forecast information; unusual-sales detection uses a statistical comparison, not a separate trained model.

**How do you prevent look-ahead bias?** Historical forecasts are requested using the day before each evaluated week. Actual sales for that week are held out for comparison.

**Does AI always win?** No. The comparison explicitly includes simple baselines and displays the best result honestly.

**Why SQLite and local AI?** The academic project has a zero-budget constraint and runs locally. This is not a production-scale deployment claim.

## Before presenting

- Run `python manage.py check` and `python manage.py test`.
- Confirm the required role can access each chosen screen.
- Confirm the database contains appropriate demo records and that the forecasting model can run.
- Verify the comparison page is populated; allow extra time for first model load.
- Avoid live data modifications that could disrupt subsequent screens.
- Treat the later UI refinement and final submission review as pending until separately completed.
