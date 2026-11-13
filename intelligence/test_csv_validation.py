from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from .csv_validation import validate_daily_sales_csv


from catalog.models import Product, Supplier
from .csv_validation import validate_product_skus


from django.test import TestCase


from .services import import_historical_daily_sales
from .models import DailySales


from unittest.mock import patch



class DailySalesCSVValidationTests(SimpleTestCase):

    def test_valid_csv(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,BRD-001,3,345.00\n'
        )

        rows = validate_daily_sales_csv(csv_text)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['date'], date(2025, 11, 10))
        self.assertEqual(rows[0]['sku'], 'BRD-001')
        self.assertEqual(rows[0]['units_sold'], 3)
        self.assertEqual(
            rows[0]['gross_revenue'],
            Decimal('345.00')
        )

    def test_empty_csv(self):
        with self.assertRaises(ValueError):
            validate_daily_sales_csv('')

    def test_wrong_columns(self):
        csv_text = 'date,sku,quantity,revenue\n'

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)

    def test_invalid_date(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-13-10,BRD-001,3,345.00\n'
        )

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)

    def test_missing_sku(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,,3,345.00\n'
        )

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)

    def test_negative_quantity(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,BRD-001,-3,345.00\n'
        )

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)

    def test_invalid_revenue(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,BRD-001,3,invalid\n'
        )

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)

    def test_duplicate_product_date(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,BRD-001,3,345.00\n'
            '2025-11-10,BRD-001,2,230.00\n'
        )

        with self.assertRaises(ValueError):
            validate_daily_sales_csv(csv_text)



class ProductSKUValidationTests(TestCase):

    def setUp(self):
        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )

        self.product = Product.objects.create(
            sku='BRD-001',
            name='Test Bread',
            category='Bakery',
            supplier=self.supplier,
            unit_price=Decimal('115.00')
        )

    def test_existing_sku_is_accepted(self):
        rows = [{
            'date': date(2025, 11, 10),
            'sku': 'BRD-001',
            'units_sold': 3,
            'gross_revenue': Decimal('345.00')
        }]

        result = validate_product_skus(rows)

        self.assertEqual(result, rows)

    def test_unknown_sku_is_rejected(self):
        rows = [{
            'date': date(2025, 11, 10),
            'sku': 'BRD-999',
            'units_sold': 3,
            'gross_revenue': Decimal('345.00')
        }]

        with self.assertRaisesRegex(
            ValueError,
            'Unknown product SKU'
        ):
            validate_product_skus(rows)

    def test_multiple_unknown_skus_are_reported(self):
        rows = [
            {'sku': 'BRD-999'},
            {'sku': 'BRD-888'}
        ]

        with self.assertRaises(ValueError) as error:
            validate_product_skus(rows)

        self.assertIn('BRD-999', str(error.exception))
        self.assertIn('BRD-888', str(error.exception))



class HistoricalSalesImportTests(TestCase):

    def setUp(self):
        self.supplier = Supplier.objects.create(
            name='Import Test Supplier'
        )

        self.product = Product.objects.create(
            sku='IMP-001',
            name='Import Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

    def test_import_creates_daily_sales(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
        )

        count = import_historical_daily_sales(csv_text)

        self.assertEqual(count, 1)
        self.assertEqual(DailySales.objects.count(), 1)

        record = DailySales.objects.get(
            product=self.product,
            date=date(2025, 11, 10)
        )

        self.assertEqual(record.units_sold, 3)
        self.assertEqual(
            record.gross_revenue,
            Decimal('150.00')
        )

    def test_reimport_updates_without_duplicates(self):
        first_csv = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
        )

        updated_csv = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,5,250.00\n'
        )

        import_historical_daily_sales(first_csv)
        import_historical_daily_sales(updated_csv)

        self.assertEqual(DailySales.objects.count(), 1)

        record = DailySales.objects.get()

        self.assertEqual(record.units_sold, 5)
        self.assertEqual(
            record.gross_revenue,
            Decimal('250.00')
        )

    def test_unknown_sku_saves_nothing(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
            '2025-11-11,IMP-999,2,100.00\n'
        )

        with self.assertRaises(ValueError):
            import_historical_daily_sales(csv_text)

        self.assertEqual(DailySales.objects.count(), 0)

    def test_import_does_not_change_stock(self):
        original_stock = self.product.on_hand

        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
        )

        import_historical_daily_sales(csv_text)

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.on_hand,
            original_stock
        )

    
    def test_database_failure_rolls_back_import(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
            '2025-11-11,IMP-001,2,100.00\n'
        )

        original_update = DailySales.objects.update_or_create
        call_count = 0

        def fail_on_second_save(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 2:
                raise RuntimeError('Simulated database failure')

            return original_update(*args, **kwargs)

        with patch.object(
            DailySales.objects,
            'update_or_create',
            side_effect=fail_on_second_save
        ):
            with self.assertRaises(RuntimeError):
                import_historical_daily_sales(csv_text)

        self.assertEqual(
            DailySales.objects.count(),
            0
        )

    
    def test_header_only_csv_is_rejected(self):
        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
        )

        with self.assertRaises(ValueError):
            import_historical_daily_sales(csv_text)

        self.assertEqual(
            DailySales.objects.count(),
            0
        )


    
    def test_import_multiple_products(self):
        second_product = Product.objects.create(
            sku='IMP-002',
            name='Second Import Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('25.00')
        )

        csv_text = (
            'date,sku,units_sold,gross_revenue\n'
            '2025-11-10,IMP-001,3,150.00\n'
            '2025-11-10,IMP-002,4,100.00\n'
        )

        count = import_historical_daily_sales(csv_text)

        self.assertEqual(count, 2)
        self.assertEqual(DailySales.objects.count(), 2)

        first_record = DailySales.objects.get(
            product=self.product
        )

        second_record = DailySales.objects.get(
            product=second_product
        )

        self.assertEqual(first_record.units_sold, 3)
        self.assertEqual(
            first_record.gross_revenue,
            Decimal('150.00')
        )

        self.assertEqual(second_record.units_sold, 4)
        self.assertEqual(
            second_record.gross_revenue,
            Decimal('100.00')
        )



