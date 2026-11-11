
from django.test import TestCase
from django.db import models

from .models import Sale, SaleLine

from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from .services import record_sale, void_sale


class SalesModelTests(TestCase):

    def test_sale_fields_exist(self):
        field_names = {
            field.name for field in Sale._meta.fields
        }

        required_fields = {
            'sale_number',
            'status',
            'discount_type',
            'discount_value',
            'subtotal',
            'total',
            'created_by',
            'created_at',
            'voided_by',
            'voided_at',
            'void_reason',
            'submission_key',
        }

        self.assertTrue(required_fields.issubset(field_names))

    def test_sale_line_fields_exist(self):
        field_names = {
            field.name for field in SaleLine._meta.fields
        }

        required_fields = {
            'sale',
            'product',
            'product_name',
            'quantity',
            'unit_price',
            'line_total',
        }

        self.assertTrue(required_fields.issubset(field_names))

    def test_sale_line_relationships_are_protected(self):
        for field_name in ['sale', 'product']:
            field = SaleLine._meta.get_field(field_name)
            self.assertEqual(field.remote_field.on_delete, models.PROTECT)




from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from inventory.services import change_stock
from .services import record_sale


class RecordSaleTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username='sales_test_user',
            email='sales_test@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )

        self.product = Product.objects.create(
            sku='SALE-001',
            name='Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.second_product = Product.objects.create(
            sku='SALE-002',
            name='Pen',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('20.00')
        )

        for product in [self.product, self.second_product]:
            change_stock(
                product_id=product.pk,
                delta=10,
                movement_type='opening',
                reason='Test opening stock',
                user=self.user
            )

    def make_sale(self, items=None, **kwargs):
        if items is None:
            items = [
                {
                    'product_id': self.product.pk,
                    'quantity': 3
                }
            ]

        kwargs.setdefault('submission_key', str(uuid4()))

        return record_sale(
            items=items,
            user=self.user,
            **kwargs
        )

    def test_sale_reduces_stock(self):
        sale = self.make_sale()

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(sale.total, Decimal('150.00'))
        self.assertEqual(sale.lines.count(), 1)

        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product,
                movement_type='sale',
                quantity_delta=-3,
                source=sale.sale_number
            ).exists()
        )

    def test_percentage_discount(self):
        sale = self.make_sale(
            discount_type='percent',
            discount_value=10
        )

        self.assertEqual(sale.subtotal, Decimal('150.00'))
        self.assertEqual(sale.total, Decimal('135.00'))

    def test_fixed_discount(self):
        sale = self.make_sale(
            discount_type='fixed',
            discount_value=Decimal('25.00')
        )

        self.assertEqual(sale.total, Decimal('125.00'))

    def test_overselling_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale([
                {
                    'product_id': self.product.pk,
                    'quantity': 11
                }
            ])

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(Sale.objects.count(), 0)

    def test_duplicate_submission_does_not_deduct_twice(self):
        key = str(uuid4())

        first = self.make_sale(submission_key=key)
        second = self.make_sale(submission_key=key)

        self.product.refresh_from_db()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(Sale.objects.count(), 1)

    def test_multiple_products_rollback_together(self):
        with self.assertRaises(ValueError):
            self.make_sale([
                {
                    'product_id': self.product.pk,
                    'quantity': 3
                },
                {
                    'product_id': self.second_product.pk,
                    'quantity': 11
                }
            ])

        self.product.refresh_from_db()
        self.second_product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(self.second_product.on_hand, 10)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleLine.objects.count(), 0)

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='sale'
            ).count(),
            0
        )

    def test_sale_keeps_product_snapshots(self):
        sale = self.make_sale()
        line = sale.lines.get()

        self.product.name = 'Updated Notebook'
        self.product.unit_price = Decimal('80.00')
        self.product.save()

        line.refresh_from_db()

        self.assertEqual(line.product_name, 'Notebook')
        self.assertEqual(line.unit_price, Decimal('50.00'))

    def test_duplicate_products_are_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale([
                {
                    'product_id': self.product.pk,
                    'quantity': 2
                },
                {
                    'product_id': self.product.pk,
                    'quantity': 1
                }
            ])

        self.assertEqual(Sale.objects.count(), 0)

    def test_discount_cannot_exceed_subtotal(self):
        with self.assertRaises(ValueError):
            self.make_sale(
                discount_type='fixed',
                discount_value=200
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save()

        with self.assertRaises(ValueError):
            self.make_sale()

        self.assertEqual(Sale.objects.count(), 0)



    def test_admin_cannot_record_sale(self):
        User = get_user_model()

        admin_user = User.objects.create_user(
            username='admin_sales_test',
            email='admin_sales@example.com',
            password='TestPassword123!',
            role='admin'
        )

        with self.assertRaises(ValueError):
            record_sale(
                items=[
                    {
                        'product_id': self.product.pk,
                        'quantity': 1
                    }
                ],
                user=admin_user,
                submission_key=str(uuid4())
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_inactive_user_cannot_record_sale(self):
        self.user.is_active = False
        self.user.save()

        with self.assertRaises(ValueError):
            self.make_sale()

        self.assertEqual(Sale.objects.count(), 0)

    def test_invalid_percentage_discount_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale(
                discount_type='percent',
                discount_value=110
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_negative_discount_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale(
                discount_type='fixed',
                discount_value=-10
            )

        self.assertEqual(Sale.objects.count(), 0)

    def test_submission_key_cannot_be_reused_by_another_user(self):
        key = str(uuid4())

        self.make_sale(submission_key=key)

        User = get_user_model()

        other_user = User.objects.create_user(
            username='other_sales_user',
            email='other_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        with self.assertRaises(ValueError):
            record_sale(
                items=[
                    {
                        'product_id': self.product.pk,
                        'quantity': 1
                    }
                ],
                user=other_user,
                submission_key=key
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(Sale.objects.count(), 1)



    def test_duplicate_key_with_different_quantity_is_rejected(self):
        key = str(uuid4())

        self.make_sale(submission_key=key)

        with self.assertRaises(ValueError):
            self.make_sale(
                items=[
                    {
                        'product_id': self.product.pk,
                        'quantity': 2
                    }
                ],
                submission_key=key
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(Sale.objects.count(), 1)

    def test_duplicate_key_with_different_discount_is_rejected(self):
        key = str(uuid4())

        self.make_sale(submission_key=key)

        with self.assertRaises(ValueError):
            self.make_sale(
                submission_key=key,
                discount_type='fixed',
                discount_value=10
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(Sale.objects.count(), 1)



    def test_multiple_products_sale_succeeds(self):
        sale = self.make_sale([
            {
                'product_id': self.product.pk,
                'quantity': 3
            },
            {
                'product_id': self.second_product.pk,
                'quantity': 2
            }
        ])

        self.product.refresh_from_db()
        self.second_product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(self.second_product.on_hand, 8)

        self.assertEqual(sale.lines.count(), 2)
        self.assertEqual(sale.subtotal, Decimal('190.00'))
        self.assertEqual(sale.total, Decimal('190.00'))

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='sale',
                source=sale.sale_number
            ).count(),
            2
        )



    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale([
                {
                    'product_id': self.product.pk,
                    'quantity': 0
                }
            ])

        self.assertEqual(Sale.objects.count(), 0)

    def test_missing_product_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale([
                {
                    'product_id': 999999,
                    'quantity': 1
                }
            ])

        self.assertEqual(Sale.objects.count(), 0)

    def test_empty_submission_key_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale(submission_key='')

        self.assertEqual(Sale.objects.count(), 0)

    def test_discount_with_extra_decimal_places_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_sale(
                discount_type='fixed',
                discount_value='10.123'
            )

        self.assertEqual(Sale.objects.count(), 0)


    def test_database_rejects_duplicate_submission_key(self):
        from django.db import IntegrityError, transaction

        sale = self.make_sale()
        original_count = Sale.objects.count()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.create(
                    sale_number='S' + uuid4().hex[:16].upper(),
                    submission_key=sale.submission_key,
                    created_by=self.user
                )

        self.assertEqual(Sale.objects.count(), original_count)

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 7)



    def test_stock_failure_rolls_back_entire_sale(self):
        from unittest.mock import patch

        original_change_stock = change_stock
        call_count = 0

        def failing_change_stock(*args, **kwargs):
            nonlocal call_count

            call_count += 1

            if call_count == 2:
                raise ValueError('Simulated stock failure')

            return original_change_stock(*args, **kwargs)

        with patch(
            'sales.services.change_stock',
            side_effect=failing_change_stock
        ):
            with self.assertRaises(ValueError):
                self.make_sale([
                    {
                        'product_id': self.product.pk,
                        'quantity': 3
                    },
                    {
                        'product_id': self.second_product.pk,
                        'quantity': 2
                    }
                ])

        self.product.refresh_from_db()
        self.second_product.refresh_from_db()

        self.assertEqual(call_count, 2)
        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(self.second_product.on_hand, 10)

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleLine.objects.count(), 0)

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='sale'
            ).count(),
            0
        )



from django.urls import reverse
from .forms import SaleForm


class SalePageTests(RecordSaleTests):

    def test_sale_form_requires_product(self):
        form = SaleForm(data={
            'discount_type': 'none',
            'discount_value': '0'
        })

        self.assertFalse(form.is_valid())

    def test_sale_form_rejects_duplicate_products(self):
        form = SaleForm(data={
            'discount_type': 'none',
            'discount_value': '0',
            'product_1': self.product.pk,
            'quantity_1': 1,
            'product_2': self.product.pk,
            'quantity_2': 2
        })

        self.assertFalse(form.is_valid())

    def test_sales_user_can_open_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Record New Sale')

    def test_post_records_sale(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))
        key = response.context['submission_key']

        response = self.client.post(reverse('sale_create'), {
            'submission_key': key,
            'discount_type': 'none',
            'discount_value': '0',
            'product_1': self.product.pk,
            'quantity_1': 2
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 8)

    def test_duplicate_post_does_not_deduct_twice(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))
        key = response.context['submission_key']

        data = {
            'submission_key': key,
            'discount_type': 'none',
            'discount_value': '0',
            'product_1': self.product.pk,
            'quantity_1': 2
        }

        self.client.post(reverse('sale_create'), data)
        self.client.post(reverse('sale_create'), data)

        self.assertEqual(Sale.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 8)

    def test_anonymous_user_cannot_open_sale_form(self):
        response = self.client.get(reverse('sale_create'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_role_cannot_open_sale_form(self):
        User = get_user_model()

        admin_user = User.objects.create_user(
            username='sale_page_admin',
            email='sale_page_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.client.force_login(admin_user)

        response = self.client.get(reverse('sale_create'))

        self.assertRedirects(response, reverse('home'))

    def test_sales_user_cannot_view_other_users_sale(self):
        sale = self.make_sale()

        User = get_user_model()

        other_user = User.objects.create_user(
            username='other_page_sales',
            email='other_page_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.client.force_login(other_user)

        response = self.client.get(
            reverse('sale_detail', args=[sale.pk])
        )

        self.assertRedirects(response, reverse('home'))



class SaleHistoryTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.sales_user = User.objects.create_user(
            username='history_sales',
            email='history_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.other_sales_user = User.objects.create_user(
            username='history_other',
            email='history_other@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.manager = User.objects.create_user(
            username='history_manager',
            email='history_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.admin_user = User.objects.create_user(
            username='history_admin',
            email='history_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.sale_one = Sale.objects.create(
            sale_number='HISTORY-001',
            submission_key=str(uuid4()),
            created_by=self.sales_user,
            total=Decimal('100.00')
        )

        self.sale_two = Sale.objects.create(
            sale_number='HISTORY-002',
            submission_key=str(uuid4()),
            created_by=self.other_sales_user,
            total=Decimal('200.00')
    )


    def test_anonymous_user_redirected(self):
        response = self.client.get(reverse('sale_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_cannot_access_history(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('sale_list'))

        self.assertRedirects(response, reverse('home'))

    def test_sales_user_sees_only_own_sales(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(reverse('sale_list'))

        self.assertContains(response, 'HISTORY-001')
        self.assertNotContains(response, 'HISTORY-002')

    def test_manager_sees_all_sales(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'))

        self.assertContains(response, 'HISTORY-001')
        self.assertContains(response, 'HISTORY-002')

    def test_search_by_sale_number(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'), {
            'search': 'HISTORY-001'
        })

        self.assertContains(response, 'HISTORY-001')
        self.assertNotContains(response, 'HISTORY-002')

    def test_search_by_employee(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'), {
            'search': 'history_other'
        })

        self.assertContains(response, 'HISTORY-002')
        self.assertNotContains(response, 'HISTORY-001')

    def test_filter_by_status(self):
        self.sale_two.status = 'voided'
        self.sale_two.save(update_fields=['status'])

        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'), {
            'status': 'voided'
        })

        self.assertContains(response, 'HISTORY-002')
        self.assertNotContains(response, 'HISTORY-001')

    def test_invalid_status_shows_all(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'), {
            'status': 'invalid'
        })

        self.assertContains(response, 'HISTORY-001')
        self.assertContains(response, 'HISTORY-002')

    def test_sales_user_cannot_bypass_filter(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(reverse('sale_list'), {
            'search': 'HISTORY-002'
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context['page_obj'].object_list),
            0
        )
        self.assertContains(response, 'No sales found.')

    def test_pagination_limits_results(self):
        for number in range(3, 15):
            Sale.objects.create(
                sale_number=f'HISTORY-{number:03}',
                submission_key=str(uuid4()),
                created_by=self.sales_user
            )

        self.client.force_login(self.manager)

        response = self.client.get(reverse('sale_list'))

        self.assertEqual(
            len(response.context['page_obj'].object_list),
            10
        )

        self.assertTrue(
            response.context['page_obj'].has_next()
        )

    def test_sales_user_cannot_view_other_sale_detail(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(
            reverse('sale_detail', args=[self.sale_two.pk])
        )

        self.assertRedirects(response, reverse('home'))

    def test_manager_can_view_other_sale_detail(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('sale_detail', args=[self.sale_two.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HISTORY-002')


class VoidSaleTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='void_manager',
            email='void_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='void_sales',
            email='void_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.admin_user = User.objects.create_user(
            username='void_admin',
            email='void_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.supplier = Supplier.objects.create(
            name='Void Test Supplier'
        )

        self.product = Product.objects.create(
            sku='VOID-001',
            name='Void Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        change_stock(
            product_id=self.product.pk,
            delta=10,
            movement_type='opening',
            reason='Test opening stock',
            user=self.manager
        )

        self.sale = record_sale(
            items=[{
                'product_id': self.product.pk,
                'quantity': 3
            }],
            user=self.sales_user,
            submission_key=str(uuid4())
        )

    def test_void_restores_stock(self):
        void_sale(
            sale_id=self.sale.pk,
            reason='Customer cancelled',
            user=self.manager
        )

        self.product.refresh_from_db()
        self.sale.refresh_from_db()

        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(self.sale.status, 'voided')

    def test_void_creates_stock_movement(self):
        void_sale(
            self.sale.pk,
            'Incorrect sale',
            self.manager
        )

        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product,
                movement_type='void',
                quantity_delta=3,
                source=self.sale.sale_number
            ).exists()
        )

    def test_void_records_audit_details(self):
        void_sale(
            self.sale.pk,
            'Wrong transaction',
            self.manager
        )

        self.sale.refresh_from_db()

        self.assertEqual(self.sale.voided_by, self.manager)
        self.assertEqual(
            self.sale.void_reason,
            'Wrong transaction'
        )
        self.assertIsNotNone(self.sale.voided_at)
        self.assertLessEqual(
            self.sale.voided_at,
            timezone.now()
        )

    def test_cannot_void_twice(self):
        void_sale(
            self.sale.pk,
            'First void',
            self.manager
        )

        with self.assertRaises(ValueError):
            void_sale(
                self.sale.pk,
                'Second void',
                self.manager
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 10)

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type='void',
                source=self.sale.sale_number
            ).count(),
            1
        )

    def test_sales_user_cannot_void(self):
        with self.assertRaises(ValueError):
            void_sale(
                self.sale.pk,
                'Not authorized',
                self.sales_user
            )

        self.sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.sale.status, 'completed')
        self.assertEqual(self.product.on_hand, 7)

    def test_admin_cannot_void(self):
        with self.assertRaises(ValueError):
            void_sale(
                self.sale.pk,
                'Not authorized',
                self.admin_user
            )

    def test_empty_reason_rejected(self):
        with self.assertRaises(ValueError):
            void_sale(
                self.sale.pk,
                '   ',
                self.manager
            )

        self.sale.refresh_from_db()

        self.assertEqual(self.sale.status, 'completed')

    def test_anonymous_user_redirected(self):
        response = self.client.get(
            reverse('sale_void', args=[self.sale.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_sales_user_cannot_access_void_page(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(
            reverse('sale_void', args=[self.sale.pk])
        )

        self.assertRedirects(response, reverse('home'))

    def test_manager_can_open_void_page(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('sale_void', args=[self.sale.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm Void')

    def test_get_request_does_not_void_sale(self):
        self.client.force_login(self.manager)

        self.client.get(
            reverse('sale_void', args=[self.sale.pk])
        )

        self.sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.sale.status, 'completed')
        self.assertEqual(self.product.on_hand, 7)

    def test_manager_can_void_through_post(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('sale_void', args=[self.sale.pk]),
            {'reason': 'Customer returned order'}
        )

        self.assertRedirects(
            response,
            reverse('sale_detail', args=[self.sale.pk])
        )

        self.sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.sale.status, 'voided')
        self.assertEqual(self.product.on_hand, 10)

    def test_post_with_empty_reason_does_not_void(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('sale_void', args=[self.sale.pk]),
            {'reason': '   '}
        )

        self.assertEqual(response.status_code, 200)

        self.sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.sale.status, 'completed')
        self.assertEqual(self.product.on_hand, 7)

    def test_void_rolls_back_if_stock_update_fails(self):
        with patch(
            'sales.services.change_stock',
            side_effect=ValueError('Stock update failed')
        ):
            with self.assertRaises(ValueError):
                void_sale(
                    self.sale.pk,
                    'Test rollback',
                    self.manager
                )

        self.sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.sale.status, 'completed')
        self.assertEqual(self.product.on_hand, 7)

        self.assertFalse(
            StockMovement.objects.filter(
                movement_type='void',
                source=self.sale.sale_number
            ).exists()
        )