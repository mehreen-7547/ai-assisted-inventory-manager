
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse



class WeeklyEvaluationViewTests(TestCase):

    def setUp(self):
        cache.clear()
        self.url = reverse('weekly_evaluation_dashboard')

    def tearDown(self):
        cache.clear()

    @patch('intelligence.views.evaluate_weekly_forecasts')
    def test_second_request_uses_cache(self, evaluate):
        evaluate.return_value = {
            'product_count': 0,
            'evaluated_product_weeks': 0,
            'skipped_product_weeks': 0,
            'rows': [],
            'mean_weekly_absolute_errors': {},
            'best_methods': [],
        }

        User = get_user_model()
        user = User.objects.create_user(
            username='evaluation_manager',
            email='evaluation_manager@example.com',
            password='testpass123',
            role='manager'
        )
        self.client.force_login(user)

        response1 = self.client.post(self.url)
        response2 = self.client.get(self.url)

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        evaluate.assert_called_once()

    @patch('intelligence.views.evaluate_weekly_forecasts')
    def test_anonymous_user_cannot_run_evaluation(self, evaluate):
        response = self.client.get(self.url)

        self.assertNotEqual(response.status_code, 200)
        evaluate.assert_not_called()


    @patch('intelligence.views.DailySales.objects.filter')
    @patch('intelligence.views.timezone.localdate')
    def test_stale_sales_history_uses_previous_sunday(self, today, sales):
        today.return_value = date(2026, 11, 24)
        sales.return_value.order_by.return_value.values_list.return_value.first.return_value = date(2026, 11, 13)
        user = get_user_model().objects.create_user(
            username='stale_history_manager', password='testpass123',
            role='manager'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.context['end_date'], date(2026, 11, 8))

    @patch('intelligence.views.DailySales.objects.filter')
    @patch('intelligence.views.timezone.localdate')
    def test_sunday_sales_history_preserves_sunday(self, today, sales):
        today.return_value = date(2026, 11, 24)
        sales.return_value.order_by.return_value.values_list.return_value.first.return_value = date(2026, 11, 22)
        user = get_user_model().objects.create_user(
            username='sunday_history_manager', password='testpass123',
            role='manager'
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.context['end_date'], date(2026, 11, 22))
