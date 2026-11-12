
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product, Supplier
from inventory.management.commands.seed_realistic_data import CATALOG
from inventory.models import StockMovement
from purchasing.models import GoodsReceipt, PurchaseOrder
from sales.models import Sale, SaleLine


class RealisticSeedSafetyTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(
            username='realistic_manager',
            email='realistic_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )
        cls.sales = User.objects.create_user(
            username='realistic_sales',
            email='realistic_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

    def test_active_manager_is_required(self):
        with self.assertRaisesMessage(CommandError, 'active Manager'):
            call_command(
                'seed_realistic_data', manager=self.sales.username,
                stdout=StringIO()
            )
        self.assertFalse(Product.objects.exists())

    def test_existing_business_data_is_never_modified(self):
        Supplier.objects.create(name='Existing Supplier')
        with self.assertRaisesMessage(CommandError, 'Business records already exist'):
            call_command(
                'seed_realistic_data', manager=self.manager.username,
                stdout=StringIO()
            )
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertFalse(Product.objects.exists())

    @patch(
        'inventory.management.commands.seed_realistic_data.record_sale',
        side_effect=ValueError('Simulated failure')
    )
    def test_generator_failure_rolls_back_everything(self, mock_sale):
        with self.assertRaisesMessage(CommandError, 'Simulated failure'):
            call_command(
                'seed_realistic_data', manager=self.manager.username,
                stdout=StringIO()
            )
        mock_sale.assert_called()
        self.assertFalse(Supplier.objects.exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(PurchaseOrder.objects.exists())
        self.assertFalse(GoodsReceipt.objects.exists())
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(StockMovement.objects.exists())


class RealisticSeedIntegrationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(
            username='realistic_integration_manager',
            email='realistic_integration_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )
        cls.sales = User.objects.create_user(
            username='realistic_integration_sales',
            email='realistic_integration_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )
        cls.today = timezone.localdate()
        cls.output = StringIO()
        call_command(
            'seed_realistic_data',
            manager=cls.manager.username,
            stdout=cls.output
        )

    def test_branded_catalog_and_supplier_links(self):
        self.assertEqual(Product.objects.count(), len(CATALOG))
        self.assertEqual(len(CATALOG), 48)
        self.assertEqual(Supplier.objects.count(), 5)
        self.assertEqual(
            len(set(Product.objects.values_list('category', flat=True))),
            5
        )
        self.assertTrue(Product.objects.filter(name__icontains='Classmate').exists())
        self.assertTrue(Product.objects.filter(name__icontains='Logitech').exists())
        self.assertTrue(Product.objects.filter(name__icontains='Dettol').exists())
        self.assertTrue(Product.objects.filter(name__icontains='Nescafe').exists())
        self.assertTrue(Product.objects.filter(name__icontains='JK Copier').exists())
        self.assertEqual(
            StockMovement.objects.filter(movement_type='opening').count(),
            48
        )
        for product in Product.objects.select_related('supplier'):
            self.assertGreater(product.on_hand, -1)
            self.assertEqual(product.supplier.is_active, True)

    def test_one_year_of_varied_sales_including_voids(self):
        self.assertGreater(Sale.objects.count(), 1600)
        self.assertLess(Sale.objects.count(), 5500)
        self.assertTrue(Sale.objects.filter(status='voided').exists())
        self.assertTrue(Sale.objects.filter(discount_type='percent').exists())
        self.assertGreater(SaleLine.objects.count(), Sale.objects.count())

        days = list(
            Sale.objects.annotate(
                day=TruncDate('created_at')
            ).values('day').annotate(
                count=Count('id')
            )
        )
        self.assertGreater(len(days), 340)
        self.assertGreater(len({x['count'] for x in days}), 8)
        earliest = Sale.objects.order_by('created_at').first().created_at.date()
        self.assertGreaterEqual(earliest, self.today - timedelta(days=364))
        self.assertFalse(
            Sale.objects.filter(created_at__date__gt=self.today).exists()
        )

    def test_orders_receipts_and_partial_delivery(self):
        self.assertGreater(PurchaseOrder.objects.count(), 12)
        self.assertGreater(GoodsReceipt.objects.count(), 8)
        self.assertTrue(
            PurchaseOrder.objects.filter(status='ordered').exists()
        )
        self.assertTrue(
            PurchaseOrder.objects.filter(status='partially_received').exists()
        )
        self.assertTrue(
            PurchaseOrder.objects.filter(status='received').exists()
        )
        for order in PurchaseOrder.objects.prefetch_related('lines'):
            for line in order.lines.all():
                self.assertLessEqual(line.quantity_received, line.quantity_ordered)

    def test_every_stock_balance_reconciles(self):
        output = StringIO()
        call_command('check_ledger', stdout=output)
        self.assertIn('Stock ledger check passed', output.getvalue())
        self.assertEqual(
            StockMovement.objects.filter(movement_type='sale').count(),
            SaleLine.objects.count()
        )
        self.assertTrue(
            StockMovement.objects.filter(movement_type='void').exists()
        )
        self.assertTrue(
            StockMovement.objects.filter(movement_type='adjustment').exists()
        )

    def test_repeat_is_rejected_and_users_preserved(self):
        users_before = get_user_model().objects.count()
        sales_before = Sale.objects.count()
        with self.assertRaisesMessage(CommandError, 'Business records already exist'):
            call_command(
                'seed_realistic_data', manager=self.manager.username,
                stdout=StringIO()
            )
        self.assertEqual(get_user_model().objects.count(), users_before)
        self.assertEqual(Sale.objects.count(), sales_before)
