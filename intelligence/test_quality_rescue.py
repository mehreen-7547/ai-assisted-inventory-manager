from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .reorder_recommendation import get_recent_average, recommend_reorder_quantity
from .forecast_evaluation import evaluate_product_forecast


class QualityRescueTests(SimpleTestCase):
    def setUp(self):
        self.end = date(2026, 11, 13)
        self.product = SimpleNamespace(id=9, name='Soap', on_hand=1, safety_stock=2, lead_time_days=7)

    @patch('intelligence.reorder_recommendation.DailySales.objects.filter')
    def test_28_day_average_includes_zero_sales(self, query):
        rows = [(self.end - timedelta(days=i), 0 if i % 2 else 2) for i in range(28)]
        query.return_value.values_list.return_value = rows
        self.assertEqual(get_recent_average(9, self.end), 1)

    @patch('intelligence.reorder_recommendation.DailySales.objects.filter')
    def test_missing_day_is_not_assumed_zero(self, query):
        query.return_value.values_list.return_value = [(self.end, 2)]
        self.assertIsNone(get_recent_average(9, self.end))

    def test_reorder_uses_larger_recent_estimate(self):
        predictions = [{'date': self.end + timedelta(days=i), 'p50': 0.1} for i in range(1, 31)]
        with patch('intelligence.reorder_recommendation.Product.objects.get', return_value=self.product),              patch('intelligence.reorder_recommendation.forecast_product_demand', return_value={'history_days': 60, 'predictions': predictions}),              patch('intelligence.reorder_recommendation.get_recent_average', return_value=2),              patch('intelligence.reorder_recommendation.PurchaseOrderLine.objects.filter') as lines:
            lines.return_value.select_related.return_value = []
            result = recommend_reorder_quantity(9, self.end)
        self.assertEqual(result['demand_basis'], 'recent_28_day_average')
        self.assertEqual(result['reorder_quantity'], 15)

    def test_reorder_keeps_ai_when_larger(self):
        predictions = [{'date': self.end + timedelta(days=i), 'p50': 3} for i in range(1, 31)]
        with patch('intelligence.reorder_recommendation.Product.objects.get', return_value=self.product),              patch('intelligence.reorder_recommendation.forecast_product_demand', return_value={'history_days': 60, 'predictions': predictions}),              patch('intelligence.reorder_recommendation.get_recent_average', return_value=1),              patch('intelligence.reorder_recommendation.PurchaseOrderLine.objects.filter') as lines:
            lines.return_value.select_related.return_value = []
            result = recommend_reorder_quantity(9, self.end)
        self.assertEqual(result['demand_basis'], 'ai_median')
        self.assertEqual(result['reorder_quantity'], 22)

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_total_unit_errors(self, sales, forecast):
        sales.return_value = [1] * 60 + [2] * 30
        cutoff = self.end - timedelta(days=30)
        forecast.return_value = {'predictions': [
            {'date': cutoff + timedelta(days=i), 'p50': 1.5}
            for i in range(1, 31)
        ]}
        result = evaluate_product_forecast(9, self.end)
        self.assertEqual(result['actual_total'], 60)
        self.assertEqual(result['ai_total'], 45)
        self.assertEqual(result['ai_total_error'], 15)
        self.assertEqual(result['baseline_total_error'], 30)
