from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from .forecast_evaluation import (
    calculate_mae,
    evaluate_product_forecast
)


class ForecastEvaluationTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 12)
        self.sales = [10] * 60 + [12] * 30

    def make_forecast(self, value=12, count=30):
        cutoff = self.end_date - timedelta(days=30)

        return {
            'predictions': [
                {
                    'date': cutoff + timedelta(days=day),
                    'p50': value
                }
                for day in range(1, count + 1)
            ]
        }

    def test_mae_calculation(self):
        result = calculate_mae(
            [10, 20, 30],
            [12, 18, 33]
        )
        self.assertEqual(result, 2.3333)

    def test_mae_rejects_invalid_sequences(self):
        with self.assertRaises(ValueError):
            calculate_mae([1, 2], [1])

        with self.assertRaises(ValueError):
            calculate_mae([], [])

        with self.assertRaises(ValueError):
            calculate_mae([1], [float('nan')])

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_chronos_beats_baseline(self, get_data, forecast):
        get_data.return_value = self.sales
        forecast.return_value = self.make_forecast()

        result = evaluate_product_forecast(
            1, self.end_date
        )

        self.assertEqual(result['ai_mae'], 0.0)
        self.assertEqual(result['baseline_mae'], 2.0)
        self.assertEqual(result['better_model'], 'chronos')

        get_data.assert_called_once_with(
            1, self.end_date, days=90
        )

        forecast.assert_called_once_with(
            1, self.end_date - timedelta(days=30)
        )

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_baseline_beats_chronos(self, get_data, forecast):
        get_data.return_value = self.sales
        forecast.return_value = self.make_forecast(value=20)

        result = evaluate_product_forecast(
            1, self.end_date
        )

        self.assertEqual(result['better_model'], 'moving_average')

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_tie(self, get_data, forecast):
        get_data.return_value = [10] * 90
        forecast.return_value = self.make_forecast(value=10)

        result = evaluate_product_forecast(
            1, self.end_date
        )

        self.assertEqual(result['better_model'], 'tie')

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_rejects_wrong_forecast_length(self, get_data, forecast):
        get_data.return_value = self.sales
        forecast.return_value = self.make_forecast(count=29)

        with self.assertRaisesRegex(
            ValueError, 'Expected 30 AI predictions'
        ):
            evaluate_product_forecast(1, self.end_date)

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_rejects_wrong_prediction_dates(self, get_data, forecast):
        get_data.return_value = self.sales
        result = self.make_forecast()
        result['predictions'][0]['date'] = self.end_date
        forecast.return_value = result

        with self.assertRaisesRegex(
            ValueError, 'AI prediction dates do not match'
        ):
            evaluate_product_forecast(1, self.end_date)

    @patch('intelligence.forecast_evaluation.forecast_product_demand')
    @patch('intelligence.forecast_evaluation.get_forecasting_data')
    def test_missing_history_stops_evaluation(
        self, get_data, forecast
    ):
        get_data.side_effect = ValueError(
            'Missing sales history'
        )

        with self.assertRaises(ValueError):
            evaluate_product_forecast(1, self.end_date)

        forecast.assert_not_called()
