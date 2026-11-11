
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from .models import PurchaseOrder, PurchaseOrderLine
from .services import change_purchase_order_status


class PurchaseManagementTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='management_manager',
            email='management_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales = User.objects.create_user(
            username='management_sales',
            email='management_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Management Supplier'
        )

        self.product = Product.objects.create(
            sku='MANAGEMENT-001',
            name='Management Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00'),
            safety_stock=10,
            lead_time_days=5
        )

        self.order = PurchaseOrder.objects.create(
            po_number='PO-MANAGEMENT-001',
            supplier=self.supplier,
            created_by=self.manager
        )

        PurchaseOrderLine.objects.create(
            purchase_order=self.order,
            product=self.product,
            quantity_ordered=4,
            unit_cost=Decimal('25.00')
        )

        self.list_url = reverse('purchase_order_list')
        self.detail_url = reverse(
            'purchase_order_detail',
            args=[self.order.pk]
        )
        self.status_url = reverse(
            'purchase_order_status',
            args=[self.order.pk]
        )

    def test_manager_can_view_list(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PO-MANAGEMENT-001')
        self.assertContains(response, 'Management Supplier')

    def test_manager_can_view_detail(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Management Test Product')
        self.assertEqual(
            response.context['order_total'],
            Decimal('100.00')
        )

    def test_sales_cannot_view_list(self):
        self.client.force_login(self.sales)

        response = self.client.get(self.list_url)

        self.assertRedirects(response, reverse('home'))

    def test_sales_cannot_view_detail(self):
        self.client.force_login(self.sales)

        response = self.client.get(self.detail_url)

        self.assertRedirects(response, reverse('home'))

    def test_anonymous_cannot_view_list(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 302)

    def test_draft_can_be_marked_ordered(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.status_url,
            {'status': 'ordered'}
        )

        self.assertRedirects(response, self.detail_url)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'ordered')

    def test_draft_can_be_cancelled(self):
        self.client.force_login(self.manager)

        self.client.post(
            self.status_url,
            {'status': 'cancelled'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')

    def test_ordered_can_be_cancelled(self):
        self.order.status = 'ordered'
        self.order.save()

        self.client.force_login(self.manager)

        self.client.post(
            self.status_url,
            {'status': 'cancelled'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')

    def test_cancelled_cannot_be_ordered(self):
        self.order.status = 'cancelled'
        self.order.save()

        self.client.force_login(self.manager)

        self.client.post(
            self.status_url,
            {'status': 'ordered'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')

    def test_received_cannot_be_cancelled(self):
        self.order.status = 'received'
        self.order.save()

        with self.assertRaises(ValueError):
            change_purchase_order_status(
                self.order.pk,
                'cancelled',
                self.manager
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'received')

    def test_sales_cannot_change_status(self):
        self.client.force_login(self.sales)

        response = self.client.post(
            self.status_url,
            {'status': 'ordered'}
        )

        self.assertRedirects(response, reverse('home'))

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'draft')

    def test_get_cannot_change_status(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 405)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'draft')

    def test_invalid_status_rejected(self):
        self.client.force_login(self.manager)

        self.client.post(
            self.status_url,
            {'status': 'received'}
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'draft')

    def test_status_change_does_not_change_stock(self):
        self.client.force_login(self.manager)

        self.client.post(
            self.status_url,
            {'status': 'ordered'}
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 0)

    def test_auto_generated_po_number(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('purchase_order_create'),
            {
                'supplier': self.supplier.pk,
                'product_1': self.product.pk,
                'quantity_1': '3',
                'unit_cost_1': '20.00'
            }
        )

        self.assertEqual(response.status_code, 302)

        new_order = PurchaseOrder.objects.exclude(
            pk=self.order.pk
        ).get()

        self.assertTrue(new_order.po_number.startswith('PO-'))
        self.assertEqual(len(new_order.po_number), 15)
        self.assertEqual(new_order.lines.count(), 1)

        self.assertRedirects(
            response,
            reverse('purchase_order_detail', args=[new_order.pk])
        )

    def test_creation_page_shows_stock_context(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('purchase_order_create')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current Stock')
        self.assertContains(response, 'Safety Stock')
        self.assertContains(response, 'Lead Time')

    def test_manager_dashboard_has_purchase_orders_link(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            reverse('purchase_order_list')
        )
