
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Supplier
from sales.models import Sale

from core.dashboard import (
    get_sales_staff_summary,
    get_sales_staff_recent_sales,
    get_sales_staff_stock_alerts
)


class SalesStaffDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.sales_user = User.objects.create_user(
            username='staff_dashboard_sales',
            email='staff_dashboard_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.other_sales = User.objects.create_user(
            username='other_dashboard_sales',
            email='other_dashboard_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.manager = User.objects.create_user(
            username='staff_dashboard_manager',
            email='staff_dashboard_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.admin = User.objects.create_user(
            username='staff_dashboard_admin',
            email='staff_dashboard_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.supplier = Supplier.objects.create(
            name='Active Supplier'
        )

        self.inactive_supplier = Supplier.objects.create(
            name='Inactive Supplier',
            is_active=False
        )

        self.today = timezone.localdate()

    def create_product(
        self, sku, stock=0, safety=5,
        active=True, supplier=None
    ):
        return Product.objects.create(
            sku=sku,
            name=sku,
            category='Test',
            supplier=supplier or self.supplier,
            unit_price=Decimal('50.00'),
            on_hand=stock,
            safety_stock=safety,
            is_active=active
        )

    def create_sale(
        self, number, user=None, days_ago=0,
        status='completed', total='100.00'
    ):
        amount = Decimal(total)

        sale = Sale.objects.create(
            sale_number=number,
            submission_key=number,
            created_by=user or self.sales_user,
            status=status,
            subtotal=amount,
            total=amount
        )

        sale_date = self.today - timedelta(
            days=days_ago
        )

        sale_time = timezone.make_aware(
            datetime.combine(
                sale_date,
                time(12, 0)
            )
        )

        Sale.objects.filter(pk=sale.pk).update(
            created_at=sale_time
        )

        return sale

    def test_summary_counts_only_own_completed_sales(self):
        self.create_sale(
            'OWN-TODAY',
            total='100.00'
        )

        self.create_sale(
            'OWN-WEEK',
            days_ago=3,
            total='40.00'
        )

        self.create_sale(
            'OTHER-TODAY',
            user=self.other_sales,
            total='500.00'
        )

        self.create_sale(
            'OWN-VOIDED',
            status='voided',
            total='200.00'
        )

        summary = get_sales_staff_summary(
            self.sales_user
        )

        self.assertEqual(summary['today_count'], 1)
        self.assertEqual(
            summary['today_total'],
            Decimal('100.00')
        )

        self.assertEqual(summary['week_count'], 2)
        self.assertEqual(
            summary['week_total'],
            Decimal('140.00')
        )

    def test_seven_day_boundaries(self):
        self.create_sale(
            'WITHIN-WEEK',
            days_ago=6,
            total='30.00'
        )

        self.create_sale(
            'OUTSIDE-WEEK',
            days_ago=7,
            total='90.00'
        )

        summary = get_sales_staff_summary(
            self.sales_user
        )

        self.assertEqual(summary['today_count'], 0)
        self.assertEqual(summary['week_count'], 1)
        self.assertEqual(
            summary['week_total'],
            Decimal('30.00')
        )

    def test_empty_sales_totals_are_zero(self):
        summary = get_sales_staff_summary(
            self.sales_user
        )

        self.assertEqual(summary['today_count'], 0)
        self.assertEqual(summary['week_count'], 0)

        self.assertEqual(
            summary['today_total'],
            Decimal('0.00')
        )

        self.assertEqual(
            summary['week_total'],
            Decimal('0.00')
        )

    def test_out_of_stock_count_uses_active_products(self):
        self.create_product('OUT', stock=0)
        self.create_product('LOW', stock=2)
        self.create_product('NORMAL', stock=10)

        self.create_product(
            'INACTIVE-PRODUCT',
            stock=0,
            active=False
        )

        self.create_product(
            'INACTIVE-SUPPLIER',
            stock=0,
            supplier=self.inactive_supplier
        )

        summary = get_sales_staff_summary(
            self.sales_user
        )

        self.assertEqual(
            summary['out_of_stock_count'],
            1
        )

    def test_stock_alerts_filter_and_order(self):
        self.create_product('LOW', stock=3)
        self.create_product('OUT', stock=0)
        self.create_product('NORMAL', stock=10)

        self.create_product(
            'INACTIVE',
            stock=0,
            active=False
        )

        self.create_product(
            'INACTIVE-SUPPLIER',
            stock=0,
            supplier=self.inactive_supplier
        )

        products = get_sales_staff_stock_alerts()

        self.assertEqual(
            [product.sku for product in products],
            ['OUT', 'LOW']
        )

    def test_stock_alerts_limited_to_eight(self):
        for number in range(12):
            self.create_product(
                f'LIMIT-{number:02d}',
                stock=0
            )

        products = get_sales_staff_stock_alerts()

        self.assertEqual(len(products), 8)
        self.assertEqual(
            products[0].sku,
            'LIMIT-00'
        )

    def test_recent_sales_are_personal_and_include_voided(self):
        self.create_sale('OWN-001')

        self.create_sale(
            'OWN-002',
            status='voided'
        )

        self.create_sale(
            'OTHER-001',
            user=self.other_sales
        )

        sales = get_sales_staff_recent_sales(
            self.sales_user
        )

        self.assertEqual(
            [sale.sale_number for sale in sales],
            ['OWN-002', 'OWN-001']
        )

        self.assertEqual(
            sales[0].status,
            'voided'
        )

    def test_recent_sales_limited_to_eight(self):
        for number in range(12):
            self.create_sale(
                f'OWN-{number:03d}'
            )

        sales = get_sales_staff_recent_sales(
            self.sales_user
        )

        self.assertEqual(len(sales), 8)
        self.assertEqual(
            sales[0].sale_number,
            'OWN-011'
        )

    def test_sales_dashboard_displays_own_information(self):
        sale = self.create_sale('VISIBLE-SALE')

        self.create_sale(
            'HIDDEN-COWORKER',
            user=self.other_sales
        )

        self.create_product(
            'EMPTY-PRODUCT',
            stock=0
        )

        self.client.force_login(self.sales_user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'My Sales Today'
        )

        self.assertContains(
            response,
            'My Sales Last 7 Days'
        )

        self.assertContains(
            response,
            'My Recent Sales'
        )

        self.assertContains(
            response,
            'Products Needing Stock Attention'
        )

        self.assertContains(
            response,
            'VISIBLE-SALE'
        )

        self.assertContains(
            response,
            'EMPTY-PRODUCT'
        )

        self.assertContains(
            response,
            reverse('sale_detail', args=[sale.pk])
        )

        self.assertNotContains(
            response,
            'HIDDEN-COWORKER'
        )

        self.assertNotContains(
            response,
            'Purchase Orders Needing Attention'
        )

        self.assertNotContains(
            response,
            'Recent Stock Movements'
        )

        self.assertNotContains(
            response,
            'Active Supplier'
        )

    def test_sales_dashboard_empty_messages(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'You have not recorded any sales yet.'
        )

        self.assertContains(
            response,
            'No products currently need stock attention.'
        )

    def test_manager_does_not_receive_sales_staff_panels(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            'My Recent Sales'
        )

        self.assertNotContains(
            response,
            'My Sales Today'
        )

        self.assertNotIn(
            'sales_staff_summary',
            response.context
        )

    def test_admin_does_not_receive_sales_staff_panels(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            'My Recent Sales'
        )

        self.assertNotContains(
            response,
            'My Sales Last 7 Days'
        )

        self.assertNotIn(
            'sales_staff_summary',
            response.context
        )
