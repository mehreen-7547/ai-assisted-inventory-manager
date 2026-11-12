
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Supplier
from purchasing.models import PurchaseOrder
from core.dashboard import get_purchase_orders_needing_attention


class PurchaseOrderDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='po_dashboard_manager',
            email='po_dashboard_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='po_dashboard_sales',
            email='po_dashboard_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Active Supplier'
        )

        self.inactive_supplier = Supplier.objects.create(
            name='Inactive Supplier',
            is_active=False
        )

        self.today = timezone.localdate()

    def create_order(
        self, number, days_from_today=None,
        status='ordered', supplier=None
    ):
        expected_date = None

        if days_from_today is not None:
            expected_date = (
                self.today
                + timedelta(days=days_from_today)
            )

        return PurchaseOrder.objects.create(
            po_number=number,
            supplier=supplier or self.supplier,
            status=status,
            expected_delivery_date=expected_date,
            created_by=self.manager
        )

    def test_only_open_orders_from_active_suppliers(self):
        self.create_order('PO-OPEN', -2)
        self.create_order(
            'PO-PARTIAL', -1,
            status='partially_received'
        )
        self.create_order('PO-DRAFT', -5, status='draft')
        self.create_order('PO-RECEIVED', -4, status='received')
        self.create_order('PO-CANCELLED', -3, status='cancelled')
        self.create_order(
            'PO-INACTIVE', -6,
            supplier=self.inactive_supplier
        )

        results = get_purchase_orders_needing_attention()
        numbers = [item['order'].po_number for item in results]

        self.assertEqual(
            numbers,
            ['PO-OPEN', 'PO-PARTIAL']
        )

    def test_overdue_orders_appear_first(self):
        self.create_order('PO-FUTURE', 3)
        self.create_order('PO-OLDER', -5)
        self.create_order('PO-RECENT', -2)
        self.create_order('PO-NO-DATE')

        results = get_purchase_orders_needing_attention()

        self.assertEqual(
            [item['order'].po_number for item in results],
            [
                'PO-OLDER',
                'PO-RECENT',
                'PO-FUTURE',
                'PO-NO-DATE'
            ]
        )

    def test_days_overdue(self):
        self.create_order('PO-LATE', -4)
        self.create_order('PO-TODAY', 0)
        self.create_order('PO-FUTURE', 2)

        results = get_purchase_orders_needing_attention()

        days = {
            item['order'].po_number: item['days_overdue']
            for item in results
        }

        self.assertEqual(days['PO-LATE'], 4)
        self.assertEqual(days['PO-TODAY'], 0)
        self.assertEqual(days['PO-FUTURE'], 0)

    def test_limit_to_five_orders(self):
        for number in range(8):
            self.create_order(
                f'PO-{number:03d}',
                -(number + 1)
            )

        results = get_purchase_orders_needing_attention()

        self.assertEqual(len(results), 5)
        self.assertEqual(
            results[0]['order'].po_number,
            'PO-007'
        )

    def test_manager_sees_panel_and_detail_link(self):
        order = self.create_order('PO-ATTENTION', -3)

        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Purchase Orders Needing Attention'
        )
        self.assertContains(response, 'PO-ATTENTION')
        self.assertContains(
            response,
            reverse('purchase_order_detail', args=[order.pk])
        )
        self.assertContains(response, 'table-danger')

    def test_sales_staff_cannot_see_panel(self):
        self.create_order('PO-PRIVATE', -3)

        self.client.force_login(self.sales_user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'Purchase Orders Needing Attention'
        )
        self.assertNotContains(response, 'PO-PRIVATE')

    def test_empty_panel_message(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'No open purchase orders need attention.'
        )
