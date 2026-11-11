
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier

from .forms import PurchaseOrderForm
from .models import PurchaseOrder, PurchaseOrderLine
from .services import create_purchase_order


class PurchaseOrderModelTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='purchase_manager',
            email='purchase_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Purchase Test Supplier'
        )

        self.product = Product.objects.create(
            sku='PURCHASE-001',
            name='Purchase Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.order = PurchaseOrder.objects.create(
            po_number='PO-001',
            supplier=self.supplier,
            created_by=self.manager
        )

    def test_purchase_order_created(self):
        self.assertEqual(self.order.po_number, 'PO-001')
        self.assertEqual(self.order.supplier, self.supplier)

    def test_default_status_is_draft(self):
        self.assertEqual(self.order.status, 'draft')

    def test_purchase_order_string(self):
        self.assertEqual(str(self.order), 'PO-001')

    def test_purchase_order_line_created(self):
        line = PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=10,
            unit_cost=Decimal('40.00')
        )

        self.assertEqual(line.quantity_ordered, 10)
        self.assertEqual(line.purchase_order, self.order)

    def test_purchase_order_has_lines(self):
        PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=5,
            unit_cost=Decimal('40.00')
        )

        self.assertEqual(self.order.lines.count(), 1)

    def test_supplier_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.supplier.delete()

    def test_product_cannot_be_deleted_when_ordered(self):
        PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=5,
            unit_cost=Decimal('40.00')
        )

        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_creating_order_does_not_change_stock(self):
        PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=10,
            unit_cost=Decimal('40.00')
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 0)


class PurchaseOrderServiceTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='po_manager',
            email='po_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='po_sales',
            email='po_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='PO Supplier'
        )

        self.other_supplier = Supplier.objects.create(
            name='Other Supplier'
        )

        self.product = Product.objects.create(
            sku='PO-PRODUCT-001',
            name='PO Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.items = [{
            'product_id': self.product.id,
            'quantity': 10,
            'unit_cost': '40.00'
        }]

    def create_order(self, **changes):
        data = {
            'po_number': 'PO-SERVICE-001',
            'supplier_id': self.supplier.id,
            'items': self.items,
            'user': self.manager
        }
        data.update(changes)
        return create_purchase_order(**data)

    def test_manager_creates_order(self):
        order = self.create_order()

        self.assertEqual(order.status, 'draft')
        self.assertEqual(order.created_by, self.manager)
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(
            order.lines.first().quantity_ordered, 10
        )

    def test_order_does_not_increase_stock(self):
        self.create_order()

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 0)

    def test_sales_staff_cannot_create_order(self):
        with self.assertRaises(ValueError):
            self.create_order(user=self.sales_user)

        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_inactive_manager_rejected(self):
        self.manager.is_active = False
        self.manager.save()

        with self.assertRaises(ValueError):
            self.create_order()

    def test_inactive_supplier_rejected(self):
        self.supplier.is_active = False
        self.supplier.save()

        with self.assertRaises(ValueError):
            self.create_order()

    def test_inactive_product_rejected(self):
        self.product.is_active = False
        self.product.save()

        with self.assertRaises(ValueError):
            self.create_order()

    def test_product_from_other_supplier_rejected(self):
        self.product.supplier = self.other_supplier
        self.product.save()

        with self.assertRaises(ValueError):
            self.create_order()

    def test_duplicate_product_rejected(self):
        with self.assertRaises(ValueError):
            self.create_order(items=self.items * 2)

        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_zero_quantity_rejected(self):
        items = [{
            'product_id': self.product.id,
            'quantity': 0,
            'unit_cost': '40.00'
        }]

        with self.assertRaises(ValueError):
            self.create_order(items=items)

    def test_decimal_quantity_rejected(self):
        items = [{
            'product_id': self.product.id,
            'quantity': Decimal('1.5'),
            'unit_cost': '40.00'
        }]

        with self.assertRaises(ValueError):
            self.create_order(items=items)

    def test_negative_cost_rejected(self):
        items = [{
            'product_id': self.product.id,
            'quantity': 10,
            'unit_cost': '-1.00'
        }]

        with self.assertRaises(ValueError):
            self.create_order(items=items)

    def test_invalid_cost_rejected(self):
        items = [{
            'product_id': self.product.id,
            'quantity': 10,
            'unit_cost': 'invalid'
        }]

        with self.assertRaises(ValueError):
            self.create_order(items=items)

    def test_duplicate_order_number_rejected(self):
        self.create_order()

        with self.assertRaises(ValueError):
            self.create_order()

        self.assertEqual(PurchaseOrder.objects.count(), 1)

    def test_empty_items_rejected(self):
        with self.assertRaises(ValueError):
            self.create_order(items=[])

    def test_missing_product_rejected(self):
        items = [{
            'product_id': 999999,
            'quantity': 10,
            'unit_cost': '40.00'
        }]

        with self.assertRaises(ValueError):
            self.create_order(items=items)

    def test_rollback_if_second_line_fails(self):
        second_product = Product.objects.create(
            sku='PO-PRODUCT-002',
            name='Second PO Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('60.00')
        )

        items = self.items + [{
            'product_id': second_product.id,
            'quantity': 5,
            'unit_cost': '45.00'
        }]

        original_create = PurchaseOrderLine.objects.create
        calls = 0

        def failing_create(**kwargs):
            nonlocal calls
            calls += 1

            if calls == 2:
                raise RuntimeError('Simulated database failure')

            return original_create(**kwargs)

        with patch.object(
            PurchaseOrderLine.objects,
            'create',
            side_effect=failing_create
        ):
            with self.assertRaises(RuntimeError):
                self.create_order(items=items)

        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseOrderLine.objects.count(), 0)

    def test_database_duplicate_number_protection(self):
        self.create_order()

        with patch.object(
            PurchaseOrder.objects,
            'filter'
        ) as mocked_filter:
            mocked_filter.return_value.exists.return_value = False

            with self.assertRaisesRegex(
                ValueError,
                'Purchase order number already exists'
            ):
                self.create_order()

        self.assertEqual(PurchaseOrder.objects.count(), 1)


class PurchaseOrderFormViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='po_form_manager',
            email='po_form_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='po_form_sales',
            email='po_form_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Form Supplier'
        )

        self.other_supplier = Supplier.objects.create(
            name='Another Supplier'
        )

        self.product1 = Product.objects.create(
            sku='PO-FORM-001',
            name='Form Product One',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.product2 = Product.objects.create(
            sku='PO-FORM-002',
            name='Form Product Two',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('60.00')
        )

        self.other_product = Product.objects.create(
            sku='PO-FORM-003',
            name='Other Supplier Product',
            category='Stationery',
            supplier=self.other_supplier,
            unit_price=Decimal('70.00')
        )

        self.url = reverse('purchase_order_create')

        self.data = {
            'po_number': 'PO-FORM-001',
            'supplier': self.supplier.pk,
            'product_1': self.product1.pk,
            'quantity_1': '10',
            'unit_cost_1': '40.00',
            'product_2': self.product2.pk,
            'quantity_2': '5',
            'unit_cost_2': '45.00'
        }

    def test_manager_can_open_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Item')
        self.assertContains(response, 'product_1')
        self.assertEqual(len(response.context['order_rows']), 1)

    def test_sales_staff_cannot_open_form(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('home'))

    def test_anonymous_user_cannot_open_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_multiple_products_saved_in_one_order(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, self.data)

        self.assertRedirects(response, reverse('home'))

        order = PurchaseOrder.objects.get(
            po_number='PO-FORM-001'
        )

        self.assertEqual(order.lines.count(), 2)
        self.assertEqual(order.status, 'draft')

        self.assertEqual(
            set(order.lines.values_list('product_id', flat=True)),
            {self.product1.pk, self.product2.pk}
        )

    def test_purchase_does_not_increase_stock(self):
        self.client.force_login(self.manager)
        self.client.post(self.url, self.data)

        self.product1.refresh_from_db()
        self.product2.refresh_from_db()

        self.assertEqual(self.product1.on_hand, 0)
        self.assertEqual(self.product2.on_hand, 0)

    def test_duplicate_product_rejected(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['product_2'] = self.product1.pk

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'The same product cannot be selected twice.'
        )
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_other_supplier_product_rejected(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['product_2'] = self.other_product.pk

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'All products must belong to the selected supplier.'
        )
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_incomplete_row_rejected(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data.pop('unit_cost_2')

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Complete product, quantity and unit cost'
        )
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_empty_rows_are_ignored(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['product_3'] = ''
        data['quantity_3'] = ''
        data['unit_cost_3'] = ''

        response = self.client.post(self.url, data)

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(PurchaseOrderLine.objects.count(), 2)

    def test_sparse_row_numbers_supported(self):
        self.client.force_login(self.manager)

        data = self.data.copy()

        data['product_5'] = data.pop('product_2')
        data['quantity_5'] = data.pop('quantity_2')
        data['unit_cost_5'] = data.pop('unit_cost_2')

        response = self.client.post(self.url, data)

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(PurchaseOrderLine.objects.count(), 2)

    def test_invalid_submission_preserves_rows(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['quantity_2'] = '0'

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['order_rows']), 2)
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_more_than_100_rows_rejected(self):
        data = {
            'po_number': 'PO-LIMIT-001',
            'supplier': self.supplier.pk
        }

        for number in range(1, 102):
            data[f'product_{number}'] = self.product1.pk
            data[f'quantity_{number}'] = '1'
            data[f'unit_cost_{number}'] = '10.00'

        form = PurchaseOrderForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn(
            'Maximum 100 product rows allowed.',
            str(form.non_field_errors())
        )

    def test_duplicate_order_number_rejected(self):
        self.client.force_login(self.manager)

        self.client.post(self.url, self.data)
        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PurchaseOrder.objects.count(), 1)

    def test_inactive_product_rejected(self):
        self.product2.is_active = False
        self.product2.save()

        self.client.force_login(self.manager)

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
