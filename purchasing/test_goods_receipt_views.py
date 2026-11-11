
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from inventory.services import change_stock
from purchasing.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine
)
from purchasing.services import (
    change_purchase_order_status,
    create_purchase_order
)


User = get_user_model()


class GoodsReceiptViewTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username='receipt_view_manager',
            email='receipt_view_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales = User.objects.create_user(
            username='receipt_view_sales',
            email='receipt_view_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Receipt View Supplier'
        )

        self.product = Product.objects.create(
            sku='RECEIPT-VIEW-001',
            name='Receipt View Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        change_stock(
            product_id=self.product.pk,
            delta=10,
            movement_type='opening',
            reason='Initial stock for receipt view tests',
            user=self.manager
        )

        self.order = create_purchase_order(
            po_number='PO-RECEIPT-VIEW-001',
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

        self.receipt_url = reverse(
            'goods_receipt_create',
            args=[self.order.pk]
        )

        self.detail_url = reverse(
            'purchase_order_detail',
            args=[self.order.pk]
        )

    def receipt_data(self, usable, damaged, key):
        line = self.order.lines.get()

        return {
            'submission_key': key,
            f'received_{line.pk}': str(usable),
            f'damaged_{line.pk}': str(damaged)
        }

    def test_manager_can_open_receipt_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.receipt_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Receive Goods')
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.order.po_number)

    def test_sales_cannot_open_receipt_form(self):
        self.client.force_login(self.sales)

        response = self.client.get(self.receipt_url)

        self.assertRedirects(
            response,
            reverse('home')
        )

    def test_anonymous_user_cannot_open_form(self):
        response = self.client.get(self.receipt_url)

        self.assertEqual(response.status_code, 302)

    def test_ordered_detail_shows_receive_button(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.detail_url)

        self.assertContains(
            response,
            self.receipt_url
        )

    def test_partial_receipt_updates_stock_and_status(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.receipt_url,
            self.receipt_data(12, 0, 'view-receipt-001')
        )

        self.assertRedirects(
            response,
            self.detail_url
        )

        self.product.refresh_from_db()
        self.order.refresh_from_db()

        line = self.order.lines.get()

        self.assertEqual(self.product.on_hand, 22)
        self.assertEqual(line.quantity_received, 12)
        self.assertEqual(
            self.order.status,
            'partially_received'
        )

        self.assertEqual(
            GoodsReceipt.objects.count(),
            1
        )

    def test_damaged_goods_do_not_increase_stock(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.receipt_url,
            self.receipt_data(7, 3, 'view-receipt-002')
        )

        self.assertRedirects(
            response,
            self.detail_url
        )

        self.product.refresh_from_db()

        line = self.order.lines.get()
        receipt_line = GoodsReceipt.objects.get().lines.get()

        self.assertEqual(self.product.on_hand, 17)
        self.assertEqual(line.quantity_received, 10)
        self.assertEqual(receipt_line.quantity_received, 7)
        self.assertEqual(receipt_line.quantity_damaged, 3)

    def test_full_receipt_completes_order(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.receipt_url,
            self.receipt_data(20, 0, 'view-receipt-003')
        )

        self.assertRedirects(
            response,
            self.detail_url
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.order.status, 'received')
        self.assertEqual(self.product.on_hand, 30)

    def test_over_receiving_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.receipt_url,
            self.receipt_data(21, 0, 'view-receipt-004')
        )

        self.assertEqual(response.status_code, 200)

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(GoodsReceipt.objects.count(), 0)

    def test_empty_receipt_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.receipt_url,
            self.receipt_data(0, 0, 'view-receipt-005')
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GoodsReceipt.objects.count(), 0)

    def test_duplicate_submission_does_not_add_stock_twice(self):
        self.client.force_login(self.manager)

        data = self.receipt_data(
            5, 0, 'view-receipt-006'
        )

        first_response = self.client.post(
            self.receipt_url,
            data
        )

        second_response = self.client.post(
            self.receipt_url,
            data
        )

        self.assertRedirects(
            first_response,
            self.detail_url
        )

        self.assertRedirects(
            second_response,
            self.detail_url
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.on_hand, 15)
        self.assertEqual(GoodsReceipt.objects.count(), 1)

        self.assertEqual(
            StockMovement.objects.filter(
                product=self.product,
                movement_type='receipt'
            ).count(),
            1
        )

    def test_draft_order_cannot_receive_goods(self):
        self.client.force_login(self.manager)

        self.order.status = 'draft'
        self.order.save(update_fields=['status'])

        response = self.client.get(self.receipt_url)

        self.assertRedirects(
            response,
            self.detail_url
        )

    def test_received_order_cannot_receive_again(self):
        self.client.force_login(self.manager)

        self.order.status = 'received'
        self.order.save(update_fields=['status'])

        response = self.client.get(self.receipt_url)

        self.assertRedirects(
            response,
            self.detail_url
        )

    def test_partial_order_can_receive_remaining_goods(self):
        self.client.force_login(self.manager)

        self.client.post(
            self.receipt_url,
            self.receipt_data(12, 0, 'view-receipt-007')
        )

        response = self.client.get(self.receipt_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Receive Goods'
        )

        self.client.post(
            self.receipt_url,
            self.receipt_data(8, 0, 'view-receipt-008')
        )

        self.product.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.product.on_hand, 30)
        self.assertEqual(self.order.status, 'received')
        self.assertEqual(GoodsReceipt.objects.count(), 2)
