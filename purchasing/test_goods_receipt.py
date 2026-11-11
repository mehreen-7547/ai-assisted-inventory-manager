
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from inventory.services import change_stock
from purchasing.models import GoodsReceipt
from purchasing.services import (
    change_purchase_order_status,
    create_purchase_order,
    receive_goods
)


User = get_user_model()


class GoodsReceiptTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username='receipt_manager',
            email='receipt_manager@example.com',
            password='testpass123',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Receipt Test Supplier'
        )

        self.product = Product.objects.create(
            sku='RECEIPT-TEST-001',
            name='Receipt Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        change_stock(
            product_id=self.product.pk,
            delta=10,
            movement_type='opening',
            reason='Initial stock for receipt tests',
            user=self.manager
        )

        self.order = create_purchase_order(
            po_number='PO-RECEIPT-001',
            supplier_id=self.supplier.pk,
            items=[{
                'product_id': self.product.pk,
                'quantity': 20,
                'unit_cost': '30.00'
            }],
            user=self.manager
        )

        change_purchase_order_status(
            self.order.pk,
            'ordered',
            self.manager
        )

    def test_partial_receipt_updates_stock(self):
        receive_goods(
            self.order.pk,
            [{
                'product_id': self.product.pk,
                'quantity_received': 12,
                'quantity_damaged': 0
            }],
            'receipt-key-001',
            self.manager
        )

        self.product.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.product.on_hand, 22)
        self.assertEqual(self.order.status, 'partially_received')

    def test_damaged_goods_do_not_increase_stock(self):
        receive_goods(
            self.order.pk,
            [{
                'product_id': self.product.pk,
                'quantity_received': 7,
                'quantity_damaged': 3
            }],
            'receipt-key-002',
            self.manager
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 17)

    def test_full_receipt_completes_order(self):
        receive_goods(
            self.order.pk,
            [{
                'product_id': self.product.pk,
                'quantity_received': 20,
                'quantity_damaged': 0
            }],
            'receipt-key-003',
            self.manager
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'received')

    def test_over_receiving_is_rejected(self):
        with self.assertRaises(ValueError):
            receive_goods(
                self.order.pk,
                [{
                    'product_id': self.product.pk,
                    'quantity_received': 21,
                    'quantity_damaged': 0
                }],
                'receipt-key-004',
                self.manager
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 10)

    def test_duplicate_submission_does_not_add_stock_twice(self):
        items = [{
            'product_id': self.product.pk,
            'quantity_received': 5,
            'quantity_damaged': 0
        }]

        receive_goods(
            self.order.pk,
            items,
            'receipt-key-005',
            self.manager
        )

        receive_goods(
            self.order.pk,
            items,
            'receipt-key-005',
            self.manager
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 15)

        self.assertEqual(
            GoodsReceipt.objects.filter(
                submission_key='receipt-key-005'
            ).count(),
            1
        )

        self.assertEqual(
            StockMovement.objects.filter(
                product=self.product,
                movement_type='receipt'
            ).count(),
            1
        )
