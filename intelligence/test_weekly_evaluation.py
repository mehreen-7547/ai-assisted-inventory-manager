
from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from .weekly_evaluation import evaluate_weekly_forecasts


class WeeklyEvaluationTests(SimpleTestCase):

    @patch('intelligence.weekly_evaluation.Product')
    @patch('intelligence.weekly_evaluation.get_forecasting_data')
    @patch('intelligence.weekly_evaluation.forecast_product_demand')
    def test_eight_weeks_and_three_methods(
        self, forecast, get_data, product_model
    ):
        product = type('ProductStub', (), {
            'pk': 1,
            'name': 'Test Product'
        })()

        products = product_model.objects.order_by.return_value
        products.__iter__.return_value = iter([product])
        products.count.return_value = 1

        get_data.return_value = [10] * 60 + [12] * 7

        def make_forecast(product_id, cutoff):
            return {
                'predictions': [
                    {
                        'date': cutoff + timedelta(days=day),
                        'p50': 12
                    }
                    for day in range(1, 31)
                ]
            }

        forecast.side_effect = make_forecast

        result = evaluate_weekly_forecasts(date(2026, 11, 15))

        self.assertEqual(result['evaluated_product_weeks'], 8)
        self.assertEqual(result['skipped_product_weeks'], 0)
        self.assertEqual(result['total_absolute_errors']['ai'], 0)
        self.assertEqual(result['total_absolute_errors']['average'], 112)
        self.assertEqual(result['total_absolute_errors']['zero'], 672)
        self.assertEqual(result['best_methods'], ['ai'])
        self.assertEqual(forecast.call_count, 8)

    @patch('intelligence.weekly_evaluation.Product')
    @patch('intelligence.weekly_evaluation.get_forecasting_data')
    @patch('intelligence.weekly_evaluation.forecast_product_demand')
    def test_missing_history_skips_week(
        self, forecast, get_data, product_model
    ):
        product = type('ProductStub', (), {
            'pk': 1,
            'name': 'Test Product'
        })()

        products = product_model.objects.order_by.return_value
        products.__iter__.return_value = iter([product])
        products.count.return_value = 1

        get_data.side_effect = ValueError('Missing sales history')

        result = evaluate_weekly_forecasts(date(2026, 11, 15))

        self.assertEqual(result['evaluated_product_weeks'], 0)
        self.assertEqual(result['skipped_product_weeks'], 8)
        self.assertEqual(result['best_methods'], [])
        forecast.assert_not_called()

    @patch('intelligence.weekly_evaluation.Product')
    @patch('intelligence.weekly_evaluation.get_forecasting_data')
    @patch('intelligence.weekly_evaluation.forecast_product_demand')
    def test_rejects_wrong_prediction_dates(
        self, forecast, get_data, product_model
    ):
        product = type('ProductStub', (), {
            'pk': 1,
            'name': 'Test Product'
        })()

        products = product_model.objects.order_by.return_value
        products.__iter__.return_value = iter([product])
        products.count.return_value = 1

        get_data.return_value = [10] * 67
        forecast.return_value = {
            'predictions': [
                {'date': date(2020, 1, 1), 'p50': 10}
                for _ in range(30)
            ]
        }

        result = evaluate_weekly_forecasts(date(2026, 11, 15))

        self.assertEqual(result['skipped_product_weeks'], 8)
        self.assertEqual(result['evaluated_product_weeks'], 0)
