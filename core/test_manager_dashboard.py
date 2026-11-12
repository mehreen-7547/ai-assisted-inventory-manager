
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Supplier
from purchasing.models import PurchaseOrder
from sales.models import Sale

from core.dashboard import get_manager_summary


class ManagerDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='dashboard_manager',
            email='dashboard_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='dashboard_sales',
            email='dashboard_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Dashboard Supplier'
        )

    def create_product(self, sku, stock, safety, active=True):
        return Product.objects.create(
            sku=sku,
            name=sku,
            category='Test',
            supplier=self.supplier,
            unit_price=Decimal('100.00'),
            on_hand=stock,
            safety_stock=safety,
            is_active=active
        )

    def test_stock_counts(self):
        self.create_product('LOW', 3, 5)
        self.create_product('EMPTY', 0, 5)
        self.create_product('NORMAL', 10, 5)
        self.create_product('INACTIVE', 0, 5, False)

        summary = get_manager_summary()

        self.assertEqual(summary['low_stock_count'], 1)
        self.assertEqual(summary['out_of_stock_count'], 1)

    def test_purchase_order_counts(self):
        today = timezone.localdate()

        PurchaseOrder.objects.create(
            po_number='PO-OVERDUE',
            supplier=self.supplier,
            status='ordered',
            expected_delivery_date=today - timedelta(days=1),
            created_by=self.manager
        )

        PurchaseOrder.objects.create(
            po_number='PO-FUTURE',
            supplier=self.supplier,
            status='partially_received',
            expected_delivery_date=today + timedelta(days=2),
            created_by=self.manager
        )

        summary = get_manager_summary()

        self.assertEqual(summary['open_orders_count'], 2)
        self.assertEqual(summary['overdue_orders_count'], 1)

    def test_sales_totals_exclude_voided(self):
        Sale.objects.create(
            sale_number='SALE-001',
            created_by=self.sales_user,
            submission_key='dashboard-key-001',
            status='completed',
            total=Decimal('250.00')
        )

        Sale.objects.create(
            sale_number='SALE-002',
            created_by=self.sales_user,
            submission_key='dashboard-key-002',
            status='voided',
            total=Decimal('500.00')
        )

        summary = get_manager_summary()

        self.assertEqual(summary['sales_today_count'], 1)
        self.assertEqual(
            summary['sales_today_total'],
            Decimal('250.00')
        )
        self.assertEqual(summary['sales_week_count'], 1)

    def test_manager_sees_cards(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Low-stock Products')
        self.assertContains(response, 'Overdue Purchase Orders')

    def test_sales_user_does_not_see_manager_cards(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Overdue Purchase Orders')
        self.assertNotIn('manager_summary', response.context)
