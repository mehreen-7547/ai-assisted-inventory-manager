
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from .models import Supplier, Product

from unittest.mock import patch
from inventory.models import StockMovement


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

    
    def test_manager_can_deactivate_product(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.product.refresh_from_db()

        self.assertFalse(self.product.is_active)
        self.assertEqual(self.product.on_hand, 0)
        self.assertRedirects(
            response,
            reverse('product_list')
        )

    def test_manager_can_reactivate_product(self):
        self.product.is_active = False
        self.product.save()

        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.product.refresh_from_db()

        self.assertTrue(self.product.is_active)
        self.assertRedirects(
            response,
            reverse('product_list')
        )

    def test_get_cannot_change_product_status(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertTrue(self.product.is_active)

    def test_sales_cannot_change_product_status(self):
        self.client.force_login(self.sales)

        response = self.client.post(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.product.refresh_from_db()

        self.assertTrue(self.product.is_active)
        self.assertRedirects(
            response,
            reverse('home')
        )

    def test_anonymous_cannot_change_product_status(self):
        response = self.client.post(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.product.is_active)

    def test_deactivated_product_remains_in_database(self):
        self.client.force_login(self.manager)

        self.client.post(
            reverse(
                'toggle_product_status',
                args=[self.product.id]
            )
        )

        self.assertTrue(
            Product.objects.filter(
                id=self.product.id
            ).exists()
        )



class ProductOpeningStockTests(TestCase):

    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            username='openingmanager',
            email='openingmanager@example.com',
            password='ManagerPass123!',
            role='manager'
        )

        self.sales = CustomUser.objects.create_user(
            username='openingsales',
            email='openingsales@example.com',
            password='SalesPass123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Opening Stock Supplier'
        )

        self.url = reverse('product_create')

        self.data = {
            'sku': 'OPEN001',
            'name': 'Opening Product',
            'category': 'Stationery',
            'supplier': self.supplier.pk,
            'unit_price': '50.00',
            'lead_time_days': 3,
            'safety_stock': 5,
            'opening_stock': 25
        }

    def test_create_product_with_opening_stock(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, self.data)

        self.assertRedirects(response, reverse('product_list'))

        product = Product.objects.get(sku='OPEN001')
        self.assertEqual(product.on_hand, 25)

        movement = StockMovement.objects.get(product=product)

        self.assertEqual(movement.movement_type, 'opening')
        self.assertEqual(movement.quantity_delta, 25)
        self.assertEqual(movement.balance_before, 0)
        self.assertEqual(movement.balance_after, 25)
        self.assertEqual(movement.created_by, self.manager)

    def test_zero_opening_stock(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['opening_stock'] = 0

        self.client.post(self.url, data)

        product = Product.objects.get(sku='OPEN001')

        self.assertEqual(product.on_hand, 0)
        self.assertFalse(
            StockMovement.objects.filter(product=product).exists()
        )

    def test_negative_opening_stock_rejected(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data['opening_stock'] = -5

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(sku='OPEN001').exists())

    def test_missing_opening_stock_rejected(self):
        self.client.force_login(self.manager)

        data = self.data.copy()
        data.pop('opening_stock')

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(sku='OPEN001').exists())

    def test_opening_stock_not_on_edit_form(self):
        self.client.force_login(self.manager)

        product = Product.objects.create(
            sku='EDIT001',
            name='Edit Product',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        response = self.client.get(
            reverse('product_edit', args=[product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="opening_stock"')

    def test_sales_cannot_create_product(self):
        self.client.force_login(self.sales)

        response = self.client.post(self.url, self.data)

        self.assertRedirects(response, reverse('home'))
        self.assertFalse(Product.objects.filter(sku='OPEN001').exists())

    def test_failed_stock_record_rolls_back_product(self):
        self.client.force_login(self.manager)

        with patch(
            'catalog.views.change_stock',
            side_effect=ValueError('Simulated stock failure')
        ):
            with self.assertRaisesMessage(
                ValueError, 'Simulated stock failure'
            ):
                self.client.post(self.url, self.data)

        self.assertFalse(Product.objects.filter(sku='OPEN001').exists())
        self.assertEqual(StockMovement.objects.count(), 0)




class ProductModeTests(TestCase):

    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            username='modemanager',
            email='modemanager@example.com',
            password='ManagerPass123!',
            role='manager'
        )

        self.sales = CustomUser.objects.create_user(
            username='modesales',
            email='modesales@example.com',
            password='SalesPass123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Mode Test Supplier'
        )

        self.product = Product.objects.create(
            sku='MODE001',
            name='Mode Test Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        self.url = reverse('product_list')

    def test_manager_normal_mode(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.context['mode'], '')
        self.assertContains(response, 'Edit Product')
        self.assertContains(response, 'Stock History')
        self.assertContains(response, 'Adjust Stock')

        self.assertNotContains(
            response,
            reverse('stock_adjustment', args=[self.product.pk])
        )

    def test_manager_edit_mode(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=edit')

        self.assertEqual(response.context['mode'], 'edit')
        self.assertContains(
            response,
            reverse('product_edit', args=[self.product.pk])
        )

    def test_manager_history_mode(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=history')

        self.assertEqual(response.context['mode'], 'history')
        self.assertContains(
            response,
            reverse('product_stock_history', args=[self.product.pk])
        )

    def test_manager_adjust_mode(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=adjust')

        self.assertEqual(response.context['mode'], 'adjust')
        self.assertContains(
            response,
            reverse('stock_adjustment', args=[self.product.pk])
        )

    def test_inactive_product_cannot_be_selected_for_adjustment(self):
        self.product.is_active = False
        self.product.save()

        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=adjust')

        self.assertNotContains(
            response,
            reverse('stock_adjustment', args=[self.product.pk])
        )

    def test_inactive_product_history_remains_available(self):
        self.product.is_active = False
        self.product.save()

        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=history')

        self.assertContains(
            response,
            reverse('product_stock_history', args=[self.product.pk])
        )

    def test_sales_cannot_activate_manager_modes(self):
        self.client.force_login(self.sales)

        for selected_mode in ['edit', 'history', 'adjust']:
            response = self.client.get(
                self.url + '?mode=' + selected_mode
            )

            self.assertEqual(response.context['mode'], '')
            self.assertNotContains(
                response,
                reverse('stock_adjustment', args=[self.product.pk])
            )

    def test_unknown_mode_is_ignored(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url + '?mode=unknown')

        self.assertEqual(response.context['mode'], '')


