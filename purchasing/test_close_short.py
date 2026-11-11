
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from inventory.services import change_stock

from purchasing.models import GoodsReceipt

from purchasing.services import (
    change_purchase_order_status,
    create_purchase_order,
    receive_goods
)


User = get_user_model()


class CloseShortTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username='close_short_manager',
            email='close_short_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales = User.objects.create_user(
            username='close_short_sales',
            email='close_short_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Close Short Supplier'
        )

        self.product = Product.objects.create(
            sku='CLOSE-SHORT-001',
            name='Close Short Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        change_stock(
            product_id=self.product.pk,
            delta=10,
            movement_type='opening',
            reason='Initial stock for close short tests',
            user=self.manager
        )

        self.order = create_purchase_order(
            po_number='PO-CLOSE-SHORT-001',
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

        self.status_url = reverse(
            'purchase_order_status',
            args=[self.order.pk]
        )

        self.detail_url = reverse(
            'purchase_order_detail',
            args=[self.order.pk]
        )

    def receive_partial_delivery(self):
        return receive_goods(
            order_id=self.order.pk,
            items=[{
                'product_id': self.product.pk,
                'quantity_received': 12,
                'quantity_damaged': 0
            }],
            submission_key='close-short-receipt-001',
            user=self.manager
        )

    def test_manager_can_close_partially_received_order(self):
        self.receive_partial_delivery()

        order = change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        self.assertEqual(order.status, 'closed_short')

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'closed_short')

    def test_close_short_preserves_stock(self):
        self.receive_partial_delivery()

        self.product.refresh_from_db()
        stock_before = self.product.on_hand

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        self.product.refresh_from_db()

        self.assertEqual(stock_before, 22)
        self.assertEqual(self.product.on_hand, stock_before)

    def test_close_short_preserves_received_quantities(self):
        self.receive_partial_delivery()

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        line = self.order.lines.get()

        self.assertEqual(line.quantity_ordered, 20)
        self.assertEqual(line.quantity_received, 12)

    def test_close_short_preserves_goods_receipts(self):
        receipt = self.receive_partial_delivery()

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        self.assertTrue(
            GoodsReceipt.objects.filter(pk=receipt.pk).exists()
        )

        self.assertEqual(
            GoodsReceipt.objects.filter(
                purchase_order=self.order
            ).count(),
            1
        )

    def test_cannot_close_order_without_partial_receipt(self):
        with self.assertRaises(ValueError):
            change_purchase_order_status(
                self.order.pk,
                'closed_short',
                self.manager
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'ordered')

    def test_sales_user_cannot_close_short(self):
        self.receive_partial_delivery()

        with self.assertRaises(ValueError):
            change_purchase_order_status(
                self.order.pk,
                'closed_short',
                self.sales
            )

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            'partially_received'
        )

    def test_closed_short_order_cannot_receive_more_goods(self):
        self.receive_partial_delivery()

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        with self.assertRaises(ValueError):
            receive_goods(
                order_id=self.order.pk,
                items=[{
                    'product_id': self.product.pk,
                    'quantity_received': 8,
                    'quantity_damaged': 0
                }],
                submission_key='close-short-receipt-002',
                user=self.manager
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 22)

    def test_cannot_close_short_twice(self):
        self.receive_partial_delivery()

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        with self.assertRaises(ValueError):
            change_purchase_order_status(
                self.order.pk,
                'closed_short',
                self.manager
            )

    def test_close_short_through_view(self):
        self.receive_partial_delivery()

        self.client.force_login(self.manager)

        response = self.client.post(
            self.status_url,
            {'status': 'closed_short'}
        )

        self.assertRedirects(
            response,
            self.detail_url
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'closed_short')

    def test_sales_cannot_close_short_through_view(self):
        self.receive_partial_delivery()

        self.client.force_login(self.sales)

        response = self.client.post(
            self.status_url,
            {'status': 'closed_short'}
        )

        self.assertRedirects(
            response,
            reverse('home')
        )

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            'partially_received'
        )

    def test_close_short_button_visible_for_partial_order(self):
        self.receive_partial_delivery()

        self.client.force_login(self.manager)

        response = self.client.get(self.detail_url)

        self.assertContains(
            response,
            'value="closed_short"'
        )

    def test_close_short_button_hidden_for_ordered_order(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.detail_url)

        self.assertNotContains(
            response,
            'value="closed_short"'
        )

    def test_close_short_button_hidden_after_closing(self):
        self.receive_partial_delivery()

        change_purchase_order_status(
            self.order.pk,
            'closed_short',
            self.manager
        )

        self.client.force_login(self.manager)

        response = self.client.get(self.detail_url)

        self.assertNotContains(
            response,
            'value="closed_short"'
        )
