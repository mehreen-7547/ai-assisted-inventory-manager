
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product, Supplier
from sales.models import Sale, SaleLine

from .models import DailySales
from .services import (
    get_product_daily_sales,
    save_product_daily_sales,
    save_all_product_daily_sales
)


class DailySalesTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='daily_manager',
            email='daily_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )

        self.product = Product.objects.create(
            sku='DAILY-001',
            name='Test Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.today = timezone.localdate()
        self.start_date = self.today - timedelta(days=2)

    def create_test_sale(
        self, number, day, quantity, status='completed'
    ):
        sale = Sale.objects.create(
            sale_number=f'DAILY-{number}',
            submission_key=f'daily-key-{number}',
            created_by=self.manager,
            status=status,
            subtotal=Decimal('50.00') * quantity,
            total=Decimal('50.00') * quantity
        )

        Sale.objects.filter(pk=sale.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(day, time(12, 0))
            )
        )

        return SaleLine.objects.create(
            sale=sale,
            product=self.product,
            product_name=self.product.name,
            quantity=quantity,
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00') * quantity
        )

    def test_multiple_sales_on_same_day_are_combined(self):
        self.create_test_sale(1, self.start_date, 2)
        self.create_test_sale(2, self.start_date, 3)

        rows = get_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.start_date
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['units_sold'], 5)
        self.assertEqual(
            rows[0]['gross_revenue'],
            Decimal('250.00')
        )

    def test_days_without_sales_return_zero(self):
        self.create_test_sale(1, self.start_date, 2)

        rows = get_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.today
        )

        self.assertEqual(len(rows), 3)

        self.assertEqual(
            [row['units_sold'] for row in rows],
            [2, 0, 0]
        )

    def test_voided_sales_are_excluded(self):
        self.create_test_sale(
            1, self.start_date, 2
        )

        self.create_test_sale(
            2, self.start_date, 10,
            status='voided'
        )

        rows = get_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.start_date
        )

        self.assertEqual(rows[0]['units_sold'], 2)
        self.assertEqual(
            rows[0]['gross_revenue'],
            Decimal('100.00')
        )

    def test_saving_twice_does_not_duplicate_records(self):
        line = self.create_test_sale(
            1, self.start_date, 2
        )

        first_count = save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.today
        )

        second_count = save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.today
        )

        self.assertEqual(first_count, 3)
        self.assertEqual(second_count, 3)

        self.assertEqual(
            DailySales.objects.filter(
                product=self.product
            ).count(),
            3
        )

        line.quantity = 4
        line.line_total = Decimal('200.00')
        line.save(update_fields=[
            'quantity',
            'line_total'
        ])

        save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.today
        )

        record = DailySales.objects.get(
            product=self.product,
            date=self.start_date
        )

        self.assertEqual(record.units_sold, 4)
        self.assertEqual(
            record.gross_revenue,
            Decimal('200.00')
        )


    def test_all_products_sync_without_duplicates(self):
        second_product = Product.objects.create(
            sku='DAILY-002',
            name='Test Pen',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('25.00')
        )

        self.create_test_sale(
            1, self.start_date, 2
        )

        first_result = save_all_product_daily_sales()

        self.assertEqual(first_result['products'], 2)
        self.assertEqual(first_result['start_date'], self.start_date)
        self.assertEqual(first_result['end_date'], self.today)
        self.assertEqual(first_result['records'], 6)

        self.assertEqual(DailySales.objects.count(), 6)

        second_result = save_all_product_daily_sales()

        self.assertEqual(second_result['records'], 6)
        self.assertEqual(DailySales.objects.count(), 6)

        second_product_units = list(
            DailySales.objects.filter(
                product=second_product
            ).order_by('date').values_list(
                'units_sold',
                flat=True
            )
        )

        self.assertEqual(
            second_product_units,
            [0, 0, 0]
        )


    def test_sync_replaces_imported_history(self):
        DailySales.objects.create(
            product=self.product,
            date=self.start_date,
            units_sold=8,
            gross_revenue=Decimal('400.00'),
            source='imported'
        )

        self.create_test_sale(
            1, self.start_date, 3
        )

        save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.start_date
        )

        record = DailySales.objects.get()

        self.assertEqual(record.units_sold, 3)
        self.assertEqual(
            record.gross_revenue,
            Decimal('150.00')
        )
        self.assertEqual(record.source, 'recorded')

    def test_sync_preserves_imported_history_outside_range(self):
        old_date = self.start_date - timedelta(days=1)

        DailySales.objects.create(
            product=self.product,
            date=old_date,
            units_sold=8,
            gross_revenue=Decimal('400.00'),
            source='imported'
        )

        save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.today
        )

        record = DailySales.objects.get(
            product=self.product,
            date=old_date
        )

        self.assertEqual(record.units_sold, 8)
        self.assertEqual(record.source, 'imported')

    def test_sync_marks_zero_sales_day_as_recorded(self):
        save_product_daily_sales(
            self.product.pk,
            self.start_date,
            self.start_date
        )

        record = DailySales.objects.get()

        self.assertEqual(record.units_sold, 0)
        self.assertEqual(record.source, 'recorded')
