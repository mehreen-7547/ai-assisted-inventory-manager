
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from core.dashboard import get_low_stock_products


class LowStockDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='low_stock_manager',
            email='low_stock_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='low_stock_sales',
            email='low_stock_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Active Supplier'
        )

        self.inactive_supplier = Supplier.objects.create(
            name='Inactive Supplier',
            is_active=False
        )

    def create_product(
        self, sku, stock, safety=5,
        active=True, supplier=None
    ):
        return Product.objects.create(
            sku=sku,
            name=sku,
            category='Test',
            supplier=supplier or self.supplier,
            unit_price=Decimal('100.00'),
            on_hand=stock,
            safety_stock=safety,
            lead_time_days=4,
            is_active=active
        )

    def test_only_low_and_out_of_stock_products(self):
        self.create_product('EMPTY', 0)
        self.create_product('LOW', 3)
        self.create_product('NORMAL', 10)
        self.create_product('INACTIVE', 0, active=False)
        self.create_product(
            'INACTIVE-SUPPLIER', 0,
            supplier=self.inactive_supplier
        )

        products = get_low_stock_products()
        skus = [product.sku for product in products]

        self.assertEqual(skus, ['EMPTY', 'LOW'])

    def test_lowest_stock_first(self):
        self.create_product('STOCK-4', 4)
        self.create_product('STOCK-0', 0)
        self.create_product('STOCK-2', 2)

        products = get_low_stock_products()

        self.assertEqual(
            [product.on_hand for product in products],
            [0, 2, 4]
        )

    def test_limit_to_ten_products(self):
        for number in range(15):
            self.create_product(
                f'PRODUCT-{number:02d}', 0
            )

        self.assertEqual(len(get_low_stock_products()), 10)

    def test_manager_sees_panel(self):
        self.create_product('EMPTY', 0)

        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Low-stock and Out-of-stock Products'
        )
        self.assertContains(response, 'EMPTY')
        self.assertContains(response, 'table-danger')

    def test_sales_staff_cannot_see_panel(self):
        self.client.force_login(self.sales_user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'Low-stock and Out-of-stock Products'
        )

    def test_empty_panel_message(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'No low-stock or out-of-stock products.'
        )
