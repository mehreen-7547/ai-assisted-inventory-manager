
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase

from catalog.models import Product, Supplier

from .models import PurchaseOrder, PurchaseOrderLine


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
        self.assertEqual(
            self.order.po_number,
            'PO-001'
        )
        self.assertEqual(
            self.order.supplier,
            self.supplier
        )

    def test_default_status_is_draft(self):
        self.assertEqual(
            self.order.status,
            'draft'
        )

    def test_purchase_order_string(self):
        self.assertEqual(
            str(self.order),
            'PO-001'
        )

    def test_purchase_order_line_created(self):
        line = PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=10,
            unit_cost=Decimal('40.00')
        )

        self.assertEqual(line.quantity_ordered, 10)
        self.assertEqual(
            line.purchase_order,
            self.order
        )

    def test_purchase_order_has_lines(self):
        PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=5,
            unit_cost=Decimal('40.00')
        )

        self.assertEqual(
            self.order.lines.count(),
            1
        )

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



from unittest.mock import patch

from django.db import IntegrityError

from .services import create_purchase_order


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
            order.lines.first().quantity_ordered,
            10
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
