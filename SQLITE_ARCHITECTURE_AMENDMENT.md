# Approved SQLite amendment — applies to project plan and mentor checklist

**Database:** SQLite now; Django reads the engine/name from `.env`. The later MySQL option remains possible but requires explicit approval, a compatible driver, migration planning and re-testing.

**Stock safety terminology:** Use **atomic conditional update**, not a database-specific locking claim.

Within `transaction.atomic()`, a stock-changing service will use a single ORM update:

```python
changed = Product.objects.filter(
    pk=product_id, on_hand__gte=quantity
).update(on_hand=F("on_hand") - quantity)
if changed == 0:
    raise InsufficientStock("Not enough stock")
```

The same transaction must record the sale and stock movement. Any later failure rolls the entire transaction back. Validate positive whole-number quantities before the update.

**What is proven in Module 0:** A temporary test model with one unit accepts one deduction, rejects the next, and stays at zero. A second test verifies rollback on failure. These are sequential database tests, not actual sale requests.

**What is NOT proven:** Under simultaneous requests, SQLite may produce a busy/locked-database error instead of letting a second request finish cleanly. Tests on SQLite do not establish production-grade concurrent write throughput. Actual sale requests, multi-line operations, idempotency, movement records, and concurrent behavior need further tests when those modules exist.

**Interview phrasing:** "I used an atomic conditional update inside a database transaction. The stock decreases only if the current quantity is sufficient. I verified the last-unit refusal and rollback in SQLite, but SQLite's limited concurrent writes remain a deployment limitation."

**Decision control:** Do not change other approved business decisions without asking the user first. This amendment changes only the database choice and stock-safety mechanism/terminology.
