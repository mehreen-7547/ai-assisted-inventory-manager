from datetime import date, timedelta
from unittest.mock import patch

import torch

from django.test import SimpleTestCase

from .forecasting import forecast_product_demand


class ForecastingTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 12)
        self.history = [5] * 60

    @patch('intelligence.forecasting.load_forecasting_model')
    @patch('intelligence.forecasting.get_forecasting_data')
    def test_generates_30_day_forecast(self, get_data, load_model):
        get_data.return_value = self.history

        output = torch.tensor(
            [[[3.0, 5.0, 7.0]] * 30]
        )
        load_model.return_value.predict_quantiles.return_value = (
            output, None
        )

        result = forecast_product_demand(
            1, self.end_date
        )

        self.assertEqual(result['forecast_days'], 30)
        self.assertEqual(len(result['predictions']), 30)
        self.assertEqual(result['predictions'][0]['p50'], 5.0)
        self.assertEqual(
            result['predictions'][0]['date'],
            self.end_date + timedelta(days=1)
        )
        self.assertEqual(
            result['predictions'][-1]['date'],
            self.end_date + timedelta(days=30)
        )

        args, kwargs = (
            load_model.return_value.predict_quantiles.call_args
        )

        self.assertEqual(tuple(args[0].shape), (1, 60))
        self.assertEqual(kwargs['prediction_length'], 30)
        self.assertEqual(
            kwargs['quantile_levels'],
            [0.1, 0.5, 0.9]
        )

    @patch('intelligence.forecasting.load_forecasting_model')
    @patch('intelligence.forecasting.get_forecasting_data')
    def test_negative_predictions_are_clamped(self, get_data, load_model):
        get_data.return_value = self.history

        output = torch.tensor(
            [[[-3.0, -1.0, 2.0]] * 30]
        )
        load_model.return_value.predict_quantiles.return_value = (
            output, None
        )

        result = forecast_product_demand(1, self.end_date)

        first = result['predictions'][0]
        self.assertEqual(first['p10'], 0.0)
        self.assertEqual(first['p50'], 0.0)
        self.assertEqual(first['p90'], 2.0)

    @patch('intelligence.forecasting.load_forecasting_model')
    @patch('intelligence.forecasting.get_forecasting_data')
    def test_rejects_wrong_output_shape(self, get_data, load_model):
        get_data.return_value = self.history

        output = torch.zeros((1, 29, 3))
        load_model.return_value.predict_quantiles.return_value = (
            output, None
        )

        with self.assertRaisesRegex(
            ValueError, 'Unexpected AI forecast shape'
        ):
            forecast_product_demand(1, self.end_date)

    @patch('intelligence.forecasting.load_forecasting_model')
    @patch('intelligence.forecasting.get_forecasting_data')
    def test_rejects_nonfinite_forecast(self, get_data, load_model):
        get_data.return_value = self.history

        output = torch.zeros((1, 30, 3))
        output[0, 0, 1] = float('nan')

        load_model.return_value.predict_quantiles.return_value = (
            output, None
        )

        with self.assertRaisesRegex(
            ValueError, 'AI forecast contains invalid numbers'
        ):
            forecast_product_demand(1, self.end_date)

    @patch('intelligence.forecasting.load_forecasting_model')
    @patch('intelligence.forecasting.get_forecasting_data')
    def test_missing_history_stops_before_model_load(
        self, get_data, load_model
    ):
        get_data.side_effect = ValueError(
            'Missing sales history'
        )

        with self.assertRaises(ValueError):
            forecast_product_demand(1, self.end_date)

        load_model.assert_not_called()
