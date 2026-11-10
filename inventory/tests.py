
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Product, Supplier
from .models import StockMovement
from .services import change_stock

from django.urls import reverse

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError


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




class StockAdjustmentTests(TestCase):

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='adjustmanager',
            email='adjustmanager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales = get_user_model().objects.create_user(
            username='adjustsales',
            email='adjustsales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Adjustment Supplier'
        )

        self.product = Product.objects.create(
            sku='ADJUST001',
            name='Adjustment Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

        change_stock(
            self.product.pk, 25, 'opening',
            'Initial stock', self.manager
        )

        self.url = reverse(
            'stock_adjustment',
            args=[self.product.pk]
        )

    def test_manager_can_open_adjustment_page(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adjustment Notebook')
        self.assertContains(response, 'Recorded Stock')

    def test_manager_can_reduce_stock(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 23,
            'reason': 'Two damaged notebooks'
        })

        self.assertRedirects(
            response,
            reverse(
                'product_stock_history',
                args=[self.product.pk]
            )
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 23)

        movement = StockMovement.objects.filter(
            product=self.product,
            movement_type='adjustment'
        ).get()

        self.assertEqual(movement.quantity_delta, -2)
        self.assertEqual(movement.balance_before, 25)
        self.assertEqual(movement.balance_after, 23)
        self.assertEqual(
            movement.reason,
            'Two damaged notebooks'
        )
        self.assertEqual(movement.created_by, self.manager)

    def test_manager_can_increase_stock(self):
        self.client.force_login(self.manager)

        self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 28,
            'reason': 'Three extra notebooks found'
        })

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 28)

        movement = StockMovement.objects.filter(
            movement_type='adjustment'
        ).get()

        self.assertEqual(movement.quantity_delta, 3)

    def test_stale_balance_is_rejected(self):
        self.client.force_login(self.manager)

        change_stock(
            self.product.pk, -1, 'sale',
            'Another transaction', self.manager
        )

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 23,
            'reason': 'Physical count'
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Stock changed since the page was opened'
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 24)

        self.assertFalse(
            StockMovement.objects.filter(
                movement_type='adjustment'
            ).exists()
        )

    def test_zero_difference_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 25,
            'reason': 'Physical count'
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            StockMovement.objects.filter(
                movement_type='adjustment'
            ).exists()
        )

    def test_negative_count_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': -2,
            'reason': 'Physical count'
        })

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 25)

    def test_missing_reason_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 23,
            'reason': ''
        })

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 25)

    def test_sales_cannot_adjust_stock(self):
        self.client.force_login(self.sales)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 23,
            'reason': 'Physical count'
        })

        self.assertRedirects(response, reverse('home'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 25)

    def test_anonymous_user_cannot_adjust_stock(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_inactive_product_cannot_be_adjusted(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])

        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'expected_balance': 25,
            'counted_quantity': 23,
            'reason': 'Physical count'
        })

        self.assertRedirects(response, reverse('product_list'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.on_hand, 25)




class StockLedgerIntegrityTests(TestCase):

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='ledgermanager',
            email='ledgermanager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Ledger Supplier'
        )

        self.product = Product.objects.create(
            sku='LEDGER001',
            name='Ledger Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price='50.00'
        )

    def test_movement_balances_are_continuous(self):
        change_stock(
            self.product.pk, 25, 'opening',
            'Opening stock', self.manager
        )

        change_stock(
            self.product.pk, -2, 'adjustment',
            'Two damaged items', self.manager
        )

        change_stock(
            self.product.pk, 3, 'adjustment',
            'Three extra items', self.manager
        )

        movements = StockMovement.objects.filter(
            product=self.product
        ).order_by('created_at', 'pk')

        previous_balance = 0

        for movement in movements:
            self.assertEqual(
                movement.balance_before,
                previous_balance
            )

            self.assertEqual(
                movement.balance_after,
                movement.balance_before + movement.quantity_delta
            )

            previous_balance = movement.balance_after

        self.assertEqual(movements.count(), 3)

    def test_latest_movement_matches_product_stock(self):
        change_stock(
            self.product.pk, 25, 'opening',
            'Opening stock', self.manager
        )

        change_stock(
            self.product.pk, -2, 'adjustment',
            'Physical count', self.manager
        )

        latest_movement = StockMovement.objects.filter(
            product=self.product
        ).order_by('-created_at', '-pk').first()

        self.product.refresh_from_db()

        self.assertEqual(
            latest_movement.balance_after,
            self.product.on_hand
        )

        self.assertEqual(self.product.on_hand, 23)


class StockLedgerCommandTests(TestCase):

    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='ledgercheckmanager',
            email='ledgercheck@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.supplier = Supplier.objects.create(
            name='Ledger Check Supplier'
        )

        self.product = Product.objects.create(
            sku='CHECK001',
            name='Ledger Check Product',
            category='General',
            supplier=self.supplier,
            unit_price='100.00'
        )

    def test_valid_ledger_passes(self):
        # Correct stock movements must pass the check.
        change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.manager
        )

        change_stock(
            self.product.pk, -3, 'adjustment',
            'Physical count', self.manager
        )

        output = StringIO()

        call_command('check_ledger', stdout=output)

        self.assertIn(
            'Stock ledger check passed',
            output.getvalue()
        )

    def test_incorrect_product_balance_fails(self):
        # Product stock must match its movement history.
        change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.manager
        )

        Product.objects.filter(
            pk=self.product.pk
        ).update(on_hand=15)

        with self.assertRaises(CommandError):
            call_command(
                'check_ledger',
                stdout=StringIO(),
                stderr=StringIO()
            )

    def test_broken_movement_arithmetic_fails(self):
        # A movement must contain correct balance arithmetic.
        movement = change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.manager
        )

        StockMovement.objects.filter(
            pk=movement.pk
        ).update(balance_after=12)

        with self.assertRaises(CommandError):
            call_command(
                'check_ledger',
                stdout=StringIO(),
                stderr=StringIO()
            )

    def test_broken_movement_continuity_fails(self):
        # Each movement must start at the previous balance.
        change_stock(
            self.product.pk, 10, 'opening',
            'Initial stock', self.manager
        )

        movement = change_stock(
            self.product.pk, -2, 'adjustment',
            'Damaged items', self.manager
        )

        StockMovement.objects.filter(
            pk=movement.pk
        ).update(balance_before=9)

        with self.assertRaises(CommandError):
            call_command(
                'check_ledger',
                stdout=StringIO(),
                stderr=StringIO()
            )
