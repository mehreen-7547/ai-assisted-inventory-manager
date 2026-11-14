
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier


class IntelligenceDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.manager = User.objects.create_user(
            username='intelligence_manager',
            email='intelligence_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='intelligence_sales',
            email='intelligence_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Dashboard Supplier'
        )

        self.product = Product.objects.create(
            sku='INT-001',
            name='Dashboard Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00'),
            lead_time_days=7,
            safety_stock=10
        )

        self.url = reverse('intelligence_dashboard')

    def test_login_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_sales_user_cannot_access(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            reverse('home'),
            fetch_redirect_response=False
        )

    def test_manager_can_open_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Demand Intelligence')
        self.assertContains(response, self.product.name)

    def test_invalid_product_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {'product': 'invalid'}
        )

        self.assertContains(
            response,
            'Please select a valid active product.'
        )

    def test_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {'product': self.product.pk}
        )

        self.assertContains(
            response,
            'Please select a valid active product.'
        )

    @patch('intelligence.views.detect_sales_anomalies')
    @patch('intelligence.views.recommend_reorder_quantity')
    @patch('intelligence.views.predict_stock_shortage')
    @patch('intelligence.views.forecast_product_demand')
    def test_all_results_are_displayed(
        self,
        forecast,
        shortage,
        reorder,
        anomalies
    ):
        forecast.return_value = {
            'forecast_days': 30,
            'model': 'Test Model',
            'predictions': []
        }

        shortage.return_value = {
            'first_safety_breach': None,
            'first_stockout': None,
            'overdue_incoming': 0,
            'unscheduled_incoming': 0
        }

        reorder.return_value = {
            'status': 'available',
            'reorder_quantity': 15,
            'method': 'ai_chronos',
            'reason': 'Reorder recommended',
            'scheduled_incoming': 0
        }

        anomalies.return_value = {
            'anomaly_count': 0,
            'analyzed_days': 30,
            'anomalies': [],
            'skipped_days': []
        }

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {'product': self.product.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Model')
        self.assertContains(response, 'Reorder recommended')
        self.assertContains(
            response,
            'No unusual sales patterns detected.'
        )

        forecast.assert_called_once()
        shortage.assert_called_once()
        reorder.assert_called_once()
        anomalies.assert_called_once()

    @patch('intelligence.views.detect_sales_anomalies')
    @patch('intelligence.views.recommend_reorder_quantity')
    @patch('intelligence.views.predict_stock_shortage')
    @patch('intelligence.views.forecast_product_demand')
    def test_forecast_failure_does_not_hide_other_results(
        self,
        forecast,
        shortage,
        reorder,
        anomalies
    ):
        forecast.side_effect = ValueError(
            'Missing history'
        )

        shortage.side_effect = ValueError(
            'Missing history'
        )

        reorder.return_value = {
            'status': 'available',
            'reorder_quantity': 8,
            'method': 'non_ai_fallback',
            'reason': 'Reorder recommended',
            'scheduled_incoming': 0
        }

        anomalies.return_value = {
            'anomaly_count': 0,
            'analyzed_days': 1,
            'anomalies': [],
            'skipped_days': []
        }

        self.client.force_login(self.manager)

        response = self.client.get(
            self.url,
            {'product': self.product.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'This analysis is currently unavailable.'
        )
        self.assertContains(
            response,
            'non_ai_fallback'
        )
        self.assertContains(
            response,
            'No unusual sales patterns detected.'
        )
