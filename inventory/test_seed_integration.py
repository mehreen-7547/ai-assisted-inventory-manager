
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product, Supplier
from core.dashboard import (
    get_daily_sales_last_seven_days,
    get_manager_summary,
    get_sales_staff_summary,
    get_top_selling_products
)
from inventory.models import StockMovement
from purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder
)
from sales.models import Sale, SaleLine

from inventory.management.commands.seed_demo_data import (
    ANOMALY_DAY_NUMBERS
)


class SeedDemoDataIntegrationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.manager = User.objects.create_user(
            username='integration_manager',
            email='integration_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        cls.sales_user = User.objects.create_user(
            username='integration_sales',
            email='integration_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        cls.today = timezone.localdate()
        cls.first_day = cls.today - timedelta(days=365)
        cls.last_day = cls.today - timedelta(days=1)

        cls.seed_output = StringIO()

        call_command(
            'seed_demo_data',
            manager=cls.manager.username,
            stdout=cls.seed_output
        )

    def test_products_suppliers_and_users(self):
        User = get_user_model()

        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Supplier.objects.count(), 3)
        self.assertEqual(Product.objects.count(), 25)

        self.assertTrue(
            self.manager.check_password('TestPassword123!')
        )

        self.assertTrue(
            self.sales_user.check_password('TestPassword123!')
        )

        categories = set(
            Product.objects.values_list(
                'category',
                flat=True
            )
        )

        self.assertEqual(categories, {
            'Stationery',
            'Office Supplies',
            'Electronics',
            'Cleaning',
            'Pantry'
        })

        self.assertEqual(
            Product.objects.filter(
                sku__startswith='DEMO-'
            ).count(),
            25
        )

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='opening'
            ).count(),
            25
        )

    def test_sales_cover_all_365_days(self):
        total_sales = Sale.objects.count()

        self.assertGreaterEqual(total_sales, 730)

        self.assertEqual(
            Sale.objects.filter(
                status='completed'
            ).count(),
            total_sales
        )

        days = list(
            Sale.objects.annotate(
                sale_day=TruncDate('created_at')
            ).values_list(
                'sale_day',
                flat=True
            ).distinct().order_by('sale_day')
        )

        expected_days = [
            self.first_day + timedelta(days=number)
            for number in range(365)
        ]

        self.assertEqual(days, expected_days)

        self.assertGreater(
            SaleLine.objects.count(),
            Sale.objects.count()
        )

        self.assertFalse(
            Sale.objects.filter(
                created_at__date__gte=self.today
            ).exists()
        )

    def test_six_anomaly_days_and_weekly_patterns(self):
        daily_counts = {
            item['sale_day']: item['count']
            for item in Sale.objects.annotate(
                sale_day=TruncDate('created_at')
            ).values(
                'sale_day'
            ).annotate(
                count=Count('id')
            )
        }

        expected_anomalies = {
            self.first_day + timedelta(days=number)
            for number in ANOMALY_DAY_NUMBERS
        }

        actual_anomalies = {
            day
            for day, count in daily_counts.items()
            if count >= 12
        }

        self.assertEqual(
            actual_anomalies,
            expected_anomalies
        )

        for day, count in daily_counts.items():
            if day in expected_anomalies:
                self.assertIn(count, [12, 13, 14])

            elif day.weekday() >= 5:
                self.assertIn(count, [3, 4])

            else:
                self.assertIn(count, [2, 3])

    def test_purchase_orders_and_goods_receipts(self):
        self.assertEqual(
            PurchaseOrder.objects.count(),
            32
        )

        self.assertEqual(
            GoodsReceipt.objects.count(),
            30
        )

        self.assertEqual(
            PurchaseOrder.objects.filter(
                status='received'
            ).count(),
            29
        )

        self.assertEqual(
            PurchaseOrder.objects.filter(
                status='ordered'
            ).count(),
            2
        )

        self.assertEqual(
            PurchaseOrder.objects.filter(
                status='partially_received'
            ).count(),
            1
        )

        orders = PurchaseOrder.objects.prefetch_related(
            'lines'
        )

        for order in orders:
            for line in order.lines.all():
                self.assertLessEqual(
                    line.quantity_received,
                    line.quantity_ordered
                )

                if order.status == 'received':
                    self.assertEqual(
                        line.quantity_received,
                        line.quantity_ordered
                    )

                elif order.status == 'ordered':
                    self.assertEqual(
                        line.quantity_received,
                        0
                    )

        open_orders = PurchaseOrder.objects.filter(
            status__in=['ordered', 'partially_received']
        )

        expected_dates = {
            self.last_day - timedelta(days=3),
            self.last_day - timedelta(days=2),
            self.last_day + timedelta(days=7)
        }

        actual_dates = set(
            open_orders.values_list(
                'expected_delivery_date',
                flat=True
            )
        )

        self.assertEqual(
            actual_dates,
            expected_dates
        )

    def test_stock_ledger_and_transaction_links(self):
        output = StringIO()

        call_command(
            'check_ledger',
            stdout=output
        )

        self.assertIn(
            'Stock ledger check passed',
            output.getvalue()
        )

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='sale'
            ).count(),
            SaleLine.objects.count()
        )

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='receipt'
            ).count(),
            GoodsReceiptLine.objects.filter(
                quantity_received__gt=0
            ).count()
        )

        for product in Product.objects.all():
            movements = StockMovement.objects.filter(
                product=product
            ).order_by(
                'created_at',
                'pk'
            )

            previous_balance = 0

            for movement in movements:
                self.assertEqual(
                    movement.balance_before,
                    previous_balance
                )

                self.assertEqual(
                    movement.balance_after,
                    movement.balance_before
                    + movement.quantity_delta
                )

                previous_balance = movement.balance_after

            self.assertEqual(
                product.on_hand,
                previous_balance
            )

            self.assertGreaterEqual(
                product.on_hand,
                0
            )

    def test_dashboards_use_generated_history(self):
        manager_summary = get_manager_summary()

        self.assertEqual(
            manager_summary['sales_today_count'],
            0
        )

        self.assertGreater(
            manager_summary['sales_week_count'],
            0
        )

        daily_sales = get_daily_sales_last_seven_days()

        self.assertEqual(len(daily_sales), 7)

        self.assertEqual(
            daily_sales[-1]['date'],
            self.today
        )

        self.assertEqual(
            daily_sales[-1]['sales_count'],
            0
        )

        self.assertEqual(
            sum(
                item['sales_count']
                for item in daily_sales
            ),
            manager_summary['sales_week_count']
        )

        self.assertGreater(
            len(get_top_selling_products()),
            0
        )

        staff_summary = get_sales_staff_summary(
            self.sales_user
        )

        self.assertGreater(
            staff_summary['week_count'],
            0
        )

        self.assertEqual(
            staff_summary['week_count'],
            manager_summary['sales_week_count']
        )

    def test_second_seed_run_is_rejected(self):
        sales_before = Sale.objects.count()
        products_before = Product.objects.count()
        orders_before = PurchaseOrder.objects.count()

        with self.assertRaisesMessage(
            CommandError,
            'Sales already exist'
        ):
            call_command(
                'seed_demo_data',
                manager=self.manager.username,
                stdout=StringIO()
            )

        self.assertEqual(
            Sale.objects.count(),
            sales_before
        )

        self.assertEqual(
            Product.objects.count(),
            products_before
        )

        self.assertEqual(
            PurchaseOrder.objects.count(),
            orders_before
        )
