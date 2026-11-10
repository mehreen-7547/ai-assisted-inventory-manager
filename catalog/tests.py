
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from .models import Supplier, Product


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



class ProductListTests(TestCase):

    def setUp(self):
        
        self.manager = CustomUser.objects.create_user(
            username='productmanager',
            email='productmanager@example.com',
            password='ManagerPass123!',
            role='manager'
        )

        self.sales = CustomUser.objects.create_user(
            username='productsales',
            email='productsales@example.com',
            password='SalesPass123!',
            role='sales'
        )

        self.admin_user = CustomUser.objects.create_user(
            username='productadmin',
            email='productadmin@example.com',
            password='AdminPass123!',
            role='admin'
        )


        self.supplier = Supplier.objects.create(
            name='Product Test Supplier'
        )

        self.product = Product.objects.create(
            sku='TEST-001',
            name='Test Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00',
            lead_time_days=5,
            safety_stock=10
        )

        self.url = reverse('product_list')

    def test_manager_can_view_products(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product')
        self.assertContains(response, 'TEST-001')

    def test_sales_can_view_products(self):
        self.client.force_login(self.sales)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product')

    def test_admin_cannot_view_products(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('home'))

    def test_anonymous_user_cannot_view_products(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_product_list_shows_stock_quantity(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertContains(response, 'On Hand')
        self.assertContains(response, 'Test Supplier')
        self.assertEqual(self.product.on_hand, 0)

    def test_empty_product_list(self):
        self.product.delete()
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertContains(response, 'No products found.')



    def test_manager_can_edit_product(self):
        # Manager can update existing product details.
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('product_edit', args=[self.product.id]),
            {
                'sku': 'TEST-001',
                'name': 'Updated Test Product',
                'category': 'Stationery',
                'supplier': self.supplier.id,
                'unit_price': '60.00',
                'lead_time_days': 7,
                'safety_stock': 15
            }
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.name,
            'Updated Test Product'
        )
        self.assertEqual(self.product.on_hand, 0)
        self.assertRedirects(
            response,
            reverse('product_list')
        )

    def test_sales_cannot_edit_product(self):
        # Sales Staff cannot modify product details.
        self.client.force_login(self.sales)

        response = self.client.get(
            reverse('product_edit', args=[self.product.id])
        )

        self.assertRedirects(
            response,
            reverse('home')
        )

    def test_product_edit_keeps_current_inactive_supplier(self):
        # Editing remains possible after supplier deactivation.
        self.supplier.is_active = False
        self.supplier.save()

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('product_edit', args=[self.product.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.supplier.name
        )

