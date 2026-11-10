
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from .models import Supplier


class SupplierStatusTests(TestCase):

    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            username='testmanager',
            email='manager@example.com',
            password='ManagerPass123!',
            role='manager'
        )

        self.sales = CustomUser.objects.create_user(
            username='testsales',
            email='sales@example.com',
            password='SalesPass123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            is_active=True
        )

        self.status_url = reverse(
            'toggle_supplier_status',
            args=[self.supplier.id]
        )

    def test_manager_can_deactivate_supplier(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.status_url)

        self.supplier.refresh_from_db()

        self.assertFalse(self.supplier.is_active)
        self.assertRedirects(
            response,
            reverse('supplier_list')
        )

    def test_manager_can_reactivate_supplier(self):
        self.supplier.is_active = False
        self.supplier.save()

        self.client.force_login(self.manager)

        response = self.client.post(self.status_url)

        self.supplier.refresh_from_db()

        self.assertTrue(self.supplier.is_active)
        self.assertRedirects(
            response,
            reverse('supplier_list')
        )

    def test_get_request_cannot_change_status(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.status_url)

        self.supplier.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertTrue(self.supplier.is_active)

    def test_sales_staff_cannot_change_status(self):
        self.client.force_login(self.sales)

        response = self.client.post(self.status_url)

        self.supplier.refresh_from_db()

        self.assertTrue(self.supplier.is_active)
        self.assertRedirects(
            response,
            reverse('home')
        )

    def test_unauthenticated_user_cannot_change_status(self):
        response = self.client.post(self.status_url)

        self.supplier.refresh_from_db()

        self.assertTrue(self.supplier.is_active)
        self.assertEqual(response.status_code, 302)

    def test_deactivated_supplier_remains_in_database(self):
        self.client.force_login(self.manager)

        self.client.post(self.status_url)

        self.assertTrue(
            Supplier.objects.filter(
                id=self.supplier.id
            ).exists()
        )
