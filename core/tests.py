"""Module 0 checks. No production inventory or sales tables exist yet."""

from django.conf import settings
from django.db import connection, models, transaction
from django.db.models import F
from django.test import TestCase, TransactionTestCase
from django.test.utils import isolate_apps
from django.urls import reverse


class ModuleZeroTests(TestCase):
    def test_home_page_is_available(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Module 0 setup is running")

    def test_local_timezone(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Kolkata")
        self.assertTrue(settings.USE_TZ)

    def test_sqlite_connection(self):
        self.assertEqual(connection.vendor, "sqlite")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)


class AtomicConditionalStockProofTests(TransactionTestCase):
    """Temporary test-only table; this is NOT the real sales module.

    The production stock service and stock-movement ledger will be built in
    Modules 3 and 4. This proves the basic SQLite conditional-update rule.
    """

    @isolate_apps("core")
    def test_second_sale_of_last_unit_is_refused(self):
        class ExampleProduct(models.Model):
            on_hand = models.PositiveIntegerField(default=0)

            class Meta:
                app_label = "core"
                db_table = "module0_example_product"

        with connection.schema_editor() as schema:
            schema.create_model(ExampleProduct)
        try:
            product = ExampleProduct.objects.create(on_hand=1)

            def attempt_sale(quantity):
                # ONE conditional SQL UPDATE inside the transaction.
                # No read-then-save sequence that could use stale stock.
                with transaction.atomic():
                    changed = ExampleProduct.objects.filter(
                        pk=product.pk,
                        on_hand__gte=quantity,
                    ).update(on_hand=F("on_hand") - quantity)
                    return changed == 1

            self.assertTrue(attempt_sale(1), "First sale should succeed")
            self.assertFalse(attempt_sale(1), "Second sale must be refused")
            product.refresh_from_db()
            self.assertEqual(product.on_hand, 0, "Stock cannot be negative")
        finally:
            with connection.schema_editor() as schema:
                schema.delete_model(ExampleProduct)

    @isolate_apps("core")
    def test_failed_transaction_restores_stock(self):
        class ExampleProduct(models.Model):
            on_hand = models.PositiveIntegerField(default=0)

            class Meta:
                app_label = "core"
                db_table = "module0_example_product_rollback"

        with connection.schema_editor() as schema:
            schema.create_model(ExampleProduct)
        try:
            product = ExampleProduct.objects.create(on_hand=2)
            with self.assertRaisesRegex(RuntimeError, "Simulated failure"):
                with transaction.atomic():
                    changed = ExampleProduct.objects.filter(
                        pk=product.pk,
                        on_hand__gte=1,
                    ).update(on_hand=F("on_hand") - 1)
                    self.assertEqual(changed, 1)
                    # Simulates failure saving a sale or movement record.
                    raise RuntimeError("Simulated failure")

            product.refresh_from_db()
            self.assertEqual(product.on_hand, 2)
        finally:
            with connection.schema_editor() as schema:
                schema.delete_model(ExampleProduct)
