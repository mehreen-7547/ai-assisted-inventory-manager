
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from inventory.services import change_stock
from sales.models import Sale

from core.dashboard import (
    get_recent_stock_movements,
    get_recent_sales
)


class RecentActivityDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='activity_manager',
            email='activity_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='activity_sales',
            email='activity_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.admin = User.objects.create_user(
            username='activity_admin',
            email='activity_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.supplier = Supplier.objects.create(
            name='Activity Supplier'
        )

        self.inactive_supplier = Supplier.objects.create(
            name='Inactive Activity Supplier',
            is_active=False
        )

        self.product = Product.objects.create(
            sku='ACT-001',
            name='Activity Product',
            category='Test',
            supplier=self.supplier,
            unit_price=Decimal('100.00'),
            safety_stock=5,
            lead_time_days=3
        )

    def create_movement(self, product=None, quantity=1):
        return change_stock(
            product_id=(product or self.product).pk,
            delta=quantity,
            movement_type='opening',
            reason='Dashboard test',
            user=self.manager
        )

    def create_sale(self, number, status='completed'):
        return Sale.objects.create(
            sale_number=number,
            submission_key=number,
            created_by=self.sales_user,
            status=status,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00')
        )

    def test_recent_movements_newest_first(self):
        self.create_movement(quantity=2)
        self.create_movement(quantity=3)
        self.create_movement(quantity=4)

        movements = get_recent_stock_movements()

        self.assertEqual(
            [movement.quantity_delta for movement in movements],
            [4, 3, 2]
        )

    def test_recent_movements_limited_to_eight(self):
        for number in range(12):
            self.create_movement(quantity=number + 1)

        movements = get_recent_stock_movements()

        self.assertEqual(len(movements), 8)
        self.assertEqual(movements[0].quantity_delta, 12)

    def test_inactive_products_and_suppliers_excluded(self):
        self.create_movement()

        inactive_product = Product.objects.create(
            sku='ACT-INACTIVE',
            name='Inactive Product',
            category='Test',
            supplier=self.supplier,
            unit_price=Decimal('50.00'),
            is_active=False
        )

        inactive_supplier_product = Product.objects.create(
            sku='ACT-SUPPLIER',
            name='Inactive Supplier Product',
            category='Test',
            supplier=self.inactive_supplier,
            unit_price=Decimal('50.00')
        )

        self.create_movement(inactive_product)
        self.create_movement(inactive_supplier_product)

        movements = get_recent_stock_movements()

        self.assertEqual(len(movements), 1)
        self.assertEqual(
            movements[0].product,
            self.product
        )

    def test_recent_sales_include_voided(self):
        self.create_sale('SALE-001')
        self.create_sale('SALE-002', status='voided')

        sales = get_recent_sales()

        self.assertEqual(
            [sale.sale_number for sale in sales],
            ['SALE-002', 'SALE-001']
        )
        self.assertEqual(sales[0].status, 'voided')

    def test_recent_sales_limited_to_five(self):
        for number in range(8):
            self.create_sale(f'SALE-{number:03d}')

        sales = get_recent_sales()

        self.assertEqual(len(sales), 5)
        self.assertEqual(sales[0].sale_number, 'SALE-007')

    def test_manager_sees_both_panels(self):
        self.create_movement(quantity=7)
        self.create_sale('SALE-MANAGER')

        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recent Stock Movements')
        self.assertContains(response, 'Recent Sales')
        self.assertContains(response, 'Activity Product')
        self.assertContains(response, 'SALE-MANAGER')

    def test_voided_sale_label_visible(self):
        self.create_sale('SALE-VOIDED', status='voided')

        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'SALE-VOIDED')
        self.assertContains(response, 'Voided')


def test_sales_staff_cannot_see_manager_activity(self):
    self.create_movement()
    self.create_sale('SALE-PRIVATE')

    Sale.objects.create(
        sale_number='MANAGER-ONLY-SALE',
        submission_key='manager-only-activity',
        created_by=self.manager,
        subtotal=Decimal('50.00'),
        total=Decimal('50.00')
    )

    self.client.force_login(self.sales_user)
    response = self.client.get(reverse('home'))

    self.assertEqual(response.status_code, 200)

    self.assertNotContains(
        response,
        'Recent Stock Movements'
    )

    self.assertNotIn(
        'recent_stock_movements',
        response.context
    )

    self.assertNotIn(
        'recent_sales',
        response.context
    )

    self.assertContains(
        response,
        'My Recent Sales'
    )

    self.assertContains(
        response,
        'SALE-PRIVATE'
    )

    self.assertNotContains(
        response,
        'MANAGER-ONLY-SALE'
    )


    def test_admin_cannot_see_manager_activity(self):
        self.create_movement()
        self.create_sale('SALE-ADMIN-PRIVATE')

        self.client.force_login(self.admin)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'Recent Stock Movements'
        )
        self.assertNotContains(
            response,
            'Recent Sales'
        )

    def test_empty_messages(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'No stock movements recorded yet.'
        )
        self.assertContains(
            response,
            'No sales recorded yet.'
        )
