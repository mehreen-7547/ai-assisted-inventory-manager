
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
