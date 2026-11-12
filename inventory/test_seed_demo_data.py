
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from purchasing.models import GoodsReceipt, PurchaseOrder
from sales.models import Sale


class SeedDemoDataCommandTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='seed_manager',
            email='seed_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='seed_sales',
            email='seed_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

    def test_manager_argument_is_required(self):
        with self.assertRaisesMessage(
            CommandError, 'Provide --manager'
        ):
            call_command(
                'seed_demo_data',
                stdout=StringIO()
            )

        self.assertEqual(Supplier.objects.count(), 0)

    def test_sales_staff_cannot_run_seed(self):
        with self.assertRaisesMessage(
            CommandError, 'active Inventory Manager'
        ):
            call_command(
                'seed_demo_data',
                manager=self.sales_user.username,
                stdout=StringIO()
            )

        self.assertFalse(Product.objects.exists())

    def test_inactive_manager_cannot_run_seed(self):
        self.manager.is_active = False
        self.manager.save(update_fields=['is_active'])

        with self.assertRaisesMessage(
            CommandError, 'active Inventory Manager'
        ):
            call_command(
                'seed_demo_data',
                manager=self.manager.username,
                stdout=StringIO()
            )

    def test_existing_sales_block_seed(self):
        Sale.objects.create(
            sale_number='EXISTING-001',
            submission_key='existing-sale',
            created_by=self.sales_user
        )

        with self.assertRaisesMessage(
            CommandError, 'Sales already exist'
        ):
            call_command(
                'seed_demo_data',
                manager=self.manager.username,
                stdout=StringIO()
            )

        self.assertEqual(Sale.objects.count(), 1)
        self.assertFalse(Supplier.objects.exists())

    def test_existing_demo_sku_blocks_seed(self):
        supplier = Supplier.objects.create(
            name='Other Supplier'
        )

        Product.objects.create(
            sku='DEMO-001',
            name='Existing Product',
            category='Existing',
            supplier=supplier,
            unit_price='10.00'
        )

        with self.assertRaisesMessage(
            CommandError, 'Demo product SKUs already exist'
        ):
            call_command(
                'seed_demo_data',
                manager=self.manager.username,
                stdout=StringIO()
            )

        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Supplier.objects.count(), 1)

    @patch(
        'inventory.management.commands.seed_demo_data.record_sale',
        side_effect=ValueError('Simulated sale failure')
    )
    def test_failure_rolls_back_everything(self, mock_sale):
        with self.assertRaisesMessage(
            CommandError, 'Simulated sale failure'
        ):
            call_command(
                'seed_demo_data',
                manager=self.manager.username,
                stdout=StringIO()
            )

        mock_sale.assert_called_once()

        self.assertFalse(Supplier.objects.exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(PurchaseOrder.objects.exists())
        self.assertFalse(GoodsReceipt.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.assertFalse(Sale.objects.exists())
