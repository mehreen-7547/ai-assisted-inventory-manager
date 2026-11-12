
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Supplier
from sales.models import Sale, SaleLine

from core.dashboard import (
    get_top_selling_products,
    get_daily_sales_last_seven_days
)


class SalesTrendsDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='trends_manager',
            email='trends_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='trends_sales',
            email='trends_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.admin = User.objects.create_user(
            username='trends_admin',
            email='trends_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.supplier = Supplier.objects.create(
            name='Trends Supplier'
        )

        self.inactive_supplier = Supplier.objects.create(
            name='Inactive Trends Supplier',
            is_active=False
        )

        self.product = self.create_product('MAIN-PRODUCT')
        self.today = timezone.localdate()

    def create_product(
        self, sku, active=True, supplier=None
    ):
        return Product.objects.create(
            sku=sku,
            name=sku,
            category='Test',
            supplier=supplier or self.supplier,
            unit_price=Decimal('10.00'),
            is_active=active
        )

    def create_sale(
        self, number, days_ago=0,
        status='completed', lines=None, total=None
    ):
        if lines is None:
            lines = [(self.product, 1)]

        subtotal = sum(
            (
                product.unit_price * quantity
                for product, quantity in lines
            ),
            Decimal('0.00')
        )

        if total is None:
            sale_total = subtotal
        else:
            sale_total = Decimal(str(total))

        discount = subtotal - sale_total

        sale = Sale.objects.create(
            sale_number=number,
            submission_key=number,
            created_by=self.sales_user,
            status=status,
            subtotal=subtotal,
            total=sale_total,
            discount_type=(
                'fixed' if discount > 0 else 'none'
            ),
            discount_value=(
                discount if discount > 0
                else Decimal('0.00')
            )
        )

        for product, quantity in lines:
            SaleLine.objects.create(
                sale=sale,
                product=product,
                product_name=product.name,
                quantity=quantity,
                unit_price=product.unit_price,
                line_total=product.unit_price * quantity
            )

        sale_date = self.today - timedelta(days=days_ago)

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

    def test_top_products_rank_by_units_and_sum_revenue(self):
        second = self.create_product('SECOND-PRODUCT')

        self.create_sale(
            'TOP-001',
            lines=[
                (self.product, 2),
                (second, 5)
            ]
        )

        self.create_sale(
            'TOP-002',
            lines=[(self.product, 4)]
        )

        results = get_top_selling_products()

        self.assertEqual(
            [item['product_label'] for item in results],
            ['MAIN-PRODUCT', 'SECOND-PRODUCT']
        )

        self.assertEqual(results[0]['units_sold'], 6)
        self.assertEqual(
            results[0]['gross_revenue'],
            Decimal('60.00')
        )

    def test_top_products_show_only_five(self):
        for number in range(1, 8):
            product = self.create_product(
                f'RANK-{number}'
            )

            self.create_sale(
                f'RANK-SALE-{number}',
                lines=[(product, number)]
            )

        results = get_top_selling_products()

        self.assertEqual(len(results), 5)
        self.assertEqual(
            results[0]['product_label'],
            'RANK-7'
        )
        self.assertEqual(
            results[-1]['product_label'],
            'RANK-3'
        )

    def test_top_products_exclude_voided_and_older_sales(self):
        self.create_sale(
            'WITHIN-30',
            days_ago=29,
            lines=[(self.product, 2)]
        )

        self.create_sale(
            'OUTSIDE-30',
            days_ago=30,
            lines=[(self.product, 20)]
        )

        self.create_sale(
            'VOIDED-30',
            status='voided',
            lines=[(self.product, 30)]
        )

        results = get_top_selling_products()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['units_sold'], 2)

    def test_top_products_require_active_product_and_supplier(self):
        inactive_product = self.create_product(
            'INACTIVE-PRODUCT',
            active=False
        )

        inactive_supplier_product = self.create_product(
            'INACTIVE-SUPPLIER-PRODUCT',
            supplier=self.inactive_supplier
        )

        self.create_sale(
            'ACTIVE-SALE',
            lines=[(self.product, 2)]
        )

        self.create_sale(
            'INACTIVE-PRODUCT-SALE',
            lines=[(inactive_product, 10)]
        )

        self.create_sale(
            'INACTIVE-SUPPLIER-SALE',
            lines=[(inactive_supplier_product, 20)]
        )

        results = get_top_selling_products()

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]['product_label'],
            'MAIN-PRODUCT'
        )

    def test_top_product_revenue_is_before_discounts(self):
        self.create_sale(
            'DISCOUNTED-SALE',
            lines=[(self.product, 4)],
            total=Decimal('30.00')
        )

        products = get_top_selling_products()
        days = get_daily_sales_last_seven_days()

        self.assertEqual(
            products[0]['gross_revenue'],
            Decimal('40.00')
        )

        self.assertEqual(
            days[-1]['total'],
            Decimal('30.00')
        )

    def test_daily_sales_covers_all_seven_dates(self):
        days = get_daily_sales_last_seven_days()

        self.assertEqual(len(days), 7)
        self.assertEqual(
            days[0]['date'],
            self.today - timedelta(days=6)
        )
        self.assertEqual(days[-1]['date'], self.today)

        for item in days:
            self.assertEqual(item['sales_count'], 0)
            self.assertEqual(
                item['total'],
                Decimal('0.00')
            )
            self.assertEqual(item['bar_percent'], 0)

    def test_daily_sales_only_completed_and_aggregates_totals(self):
        self.create_sale(
            'TODAY-001',
            lines=[(self.product, 3)]
        )

        self.create_sale(
            'TODAY-002',
            lines=[(self.product, 2)]
        )

        self.create_sale(
            'TODAY-VOIDED',
            status='voided',
            lines=[(self.product, 9)]
        )

        self.create_sale(
            'YESTERDAY-001',
            days_ago=1
        )

        days = get_daily_sales_last_seven_days()

        self.assertEqual(days[-1]['sales_count'], 2)
        self.assertEqual(
            days[-1]['total'],
            Decimal('50.00')
        )

        self.assertEqual(days[-2]['sales_count'], 1)
        self.assertEqual(
            days[-2]['total'],
            Decimal('10.00')
        )

    def test_daily_sales_includes_first_day_and_excludes_previous(self):
        self.create_sale(
            'FIRST-DAY',
            days_ago=6,
            lines=[(self.product, 2)]
        )

        self.create_sale(
            'BEFORE-WINDOW',
            days_ago=7,
            lines=[(self.product, 10)]
        )

        days = get_daily_sales_last_seven_days()

        self.assertEqual(days[0]['sales_count'], 1)
        self.assertEqual(
            days[0]['total'],
            Decimal('20.00')
        )

        self.assertEqual(
            sum(item['sales_count'] for item in days),
            1
        )

    def test_daily_sales_bar_percentages(self):
        self.create_sale(
            'HIGHEST-DAY',
            lines=[(self.product, 10)]
        )

        self.create_sale(
            'HALF-DAY',
            days_ago=1,
            lines=[(self.product, 5)]
        )

        days = get_daily_sales_last_seven_days()

        self.assertEqual(days[-1]['bar_percent'], 100)
        self.assertEqual(days[-2]['bar_percent'], 50)
        self.assertEqual(days[0]['bar_percent'], 0)

    def test_manager_sees_panels_only(self):
        self.create_sale(
            'VISIBLE-SALE',
            lines=[(self.product, 3)]
        )

        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Top-selling Products (Last 30 Days)'
        )
        self.assertContains(
            response,
            'Daily Sales (Last 7 Days)'
        )
        self.assertContains(response, 'MAIN-PRODUCT')
        self.assertContains(
            response,
            'Gross Revenue (Before Discounts)'
        )

        for user in [self.sales_user, self.admin]:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('home'))

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(
                    response,
                    'Top-selling Products (Last 30 Days)'
                )
                self.assertNotContains(
                    response,
                    'Daily Sales (Last 7 Days)'
                )
                self.assertNotIn(
                    'top_selling_products',
                    response.context
                )

    def test_manager_empty_messages(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'No completed product sales in the last 30 days.'
        )

        self.assertContains(
            response,
            'No completed sales in the last 7 days.'
        )
