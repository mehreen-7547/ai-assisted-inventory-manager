
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Product, Supplier
from .models import StockMovement
from .services import change_stock

from django.urls import reverse

class StockServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='stockmanager',
            email='stockmanager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Test Supplier'
        )

        self.product = Product.objects.create(
            sku='STOCK001',
            name='Test Product',
            category='General',
            supplier=self.supplier,
            unit_price='100.00'
        )

    def test_opening_stock_creates_movement(self):
        # Adding stock updates the balance and creates history.
        movement = change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.user
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 10)
        self.assertEqual(movement.balance_before, 0)
        self.assertEqual(movement.balance_after, 10)
        self.assertEqual(movement.quantity_delta, 10)

    def test_stock_reduction(self):
        # A valid reduction updates stock correctly.
        change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.user
        )
        change_stock(
            self.product.pk, -3, 'sale',
            'Test sale', self.user
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 7)
        self.assertEqual(StockMovement.objects.count(), 2)

    def test_insufficient_stock_is_rejected(self):
        # Stock cannot become negative.
        with self.assertRaisesMessage(
            ValueError, 'Not enough stock'
        ):
            change_stock(
                self.product.pk, -1, 'sale',
                'Test sale', self.user
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_zero_change_is_rejected(self):
        # A movement must change the stock quantity.
        with self.assertRaises(ValueError):
            change_stock(
                self.product.pk, 0, 'adjustment',
                'No change', self.user
            )

    def test_missing_reason_is_rejected(self):
        # Every movement needs an explanation.
        with self.assertRaises(ValueError):
            change_stock(
                self.product.pk, 5, 'opening',
                '', self.user
            )

    def test_invalid_movement_type_is_rejected(self):
        # Unknown movement types cannot enter the ledger.
        with self.assertRaises(ValueError):
            change_stock(
                self.product.pk, 5, 'unknown',
                'Test', self.user
            )

    
    def test_failed_movement_rolls_back_stock(self):
        # A failed history insert must restore the stock balance.
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            change_stock(
                self.product.pk, 5, 'opening',
                'Test', None
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 0)
        self.assertEqual(StockMovement.objects.count(), 0)



class StockHistoryTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='historymanager',
            email='historymanager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales = get_user_model().objects.create_user(
            username='historysales',
            email='historysales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.admin_user = get_user_model().objects.create_user(
            username='historyadmin',
            email='historyadmin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.supplier = Supplier.objects.create(
            name='History Supplier'
        )

        self.product = Product.objects.create(
            sku='HISTORY001',
            name='History Product',
            category='General',
            supplier=self.supplier,
            unit_price='100.00'
        )

        self.url = reverse(
            'product_stock_history',
            args=[self.product.pk]
        )

    def test_manager_can_view_history(self):
        # Managers can see movements and their details.
        change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.manager
        )

        self.client.force_login(self.manager)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'History Product')
        self.assertContains(response, 'Initial stock')
        self.assertContains(response, 'historymanager')

    def test_empty_history_page(self):
        # Products without movements show an empty-state message.
        self.client.force_login(self.manager)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'No stock movements recorded yet.'
        )

    def test_sales_staff_cannot_view_history(self):
        # Sales staff cannot access the manager's ledger page.
        self.client.force_login(self.sales)
        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('home'))

    def test_admin_cannot_view_history(self):
        # Admin accounts have no stock-management permissions.
        self.client.force_login(self.admin_user)
        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('home'))

    def test_anonymous_user_redirected(self):
        # Unauthenticated visitors must log in.
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_inactive_product_history_remains_visible(self):
        # Deactivating a product does not erase its history.
        change_stock(
            self.product.pk, 5, 'opening',
            'Initial stock', self.manager
        )

        self.product.is_active = False
        self.product.save(update_fields=['is_active'])

        self.client.force_login(self.manager)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Initial stock')

    def test_unknown_product_returns_404(self):
        # A missing product cannot display a history page.
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('product_stock_history', args=[999999])
        )

        self.assertEqual(response.status_code, 404)


