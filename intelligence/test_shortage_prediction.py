from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .shortage_prediction import predict_stock_shortage


class StockShortagePredictionTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 13)
        self.product = SimpleNamespace(
            id=30,
            name='Test Notebook',
            on_hand=20,
            safety_stock=5,
            lead_time_days=7
        )

    def make_forecast(self, demand=5):
        return {
            'predictions': [
                {
                    'date': self.end_date + timedelta(days=day),
                    'p50': demand
                }
                for day in range(1, 31)
            ]
        }

    def make_line(self, status, delivery_date, ordered, received=0):
        return SimpleNamespace(
            quantity_ordered=ordered,
            quantity_received=received,
            purchase_order=SimpleNamespace(
                status=status,
                expected_delivery_date=delivery_date
            )
        )

    def run_prediction(self, lines=None, demand=5):
        with patch(
            'intelligence.shortage_prediction.Product.objects.get'
        ) as get_product, patch(
            'intelligence.shortage_prediction.forecast_product_demand'
        ) as forecast, patch(
            'intelligence.shortage_prediction.PurchaseOrderLine.objects.filter'
        ) as filter_lines:

            get_product.return_value = self.product
            forecast.return_value = self.make_forecast(demand)

            filter_lines.return_value.select_related.return_value = (
                lines if lines is not None else []
            )

            return predict_stock_shortage(30, self.end_date)

    def test_shortage_without_incoming_stock(self):
        result = self.run_prediction()

        self.assertEqual(
            result['first_safety_breach'],
            date(2026, 11, 17)
        )
        self.assertEqual(
            result['first_stockout'],
            date(2026, 11, 18)
        )

    def test_dated_incoming_prevents_early_shortage(self):
        delivery = self.end_date + timedelta(days=3)

        line = self.make_line(
            'ordered', delivery, 30
        )

        result = self.run_prediction([line])

        self.assertEqual(
            result['daily_projection'][2]['incoming'],
            30
        )
        self.assertEqual(
            result['first_safety_breach'],
            date(2026, 11, 23)
        )

    def test_partial_receipt_counts_only_remaining(self):
        delivery = self.end_date + timedelta(days=1)

        line = self.make_line(
            'partially_received',
            delivery,
            ordered=20,
            received=12
        )

        result = self.run_prediction([line], demand=0)

        self.assertEqual(
            result['daily_projection'][0]['incoming'],
            8
        )
        self.assertEqual(
            result['daily_projection'][0]['projected_stock'],
            28
        )

    def test_undated_incoming_is_reported_separately(self):
        line = self.make_line(
            'ordered',
            None,
            ordered=25
        )

        result = self.run_prediction([line])

        self.assertEqual(result['unscheduled_incoming'], 25)
        self.assertEqual(
            result['daily_projection'][0]['incoming'],
            0
        )

    def test_multiple_deliveries_on_same_day(self):
        delivery = self.end_date + timedelta(days=1)

        lines = [
            self.make_line('ordered', delivery, 10),
            self.make_line('ordered', delivery, 15)
        ]

        result = self.run_prediction(lines, demand=0)

        self.assertEqual(
            result['daily_projection'][0]['incoming'],
            25
        )

    def test_no_shortage_when_demand_is_zero(self):
        result = self.run_prediction(demand=0)

        self.assertIsNone(result['first_safety_breach'])
        self.assertIsNone(result['first_stockout'])
        self.assertEqual(
            result['daily_projection'][-1]['projected_stock'],
            20
        )

    def test_overdue_delivery_is_excluded(self):
        overdue_date = self.end_date - timedelta(days=2)

        line = self.make_line(
            'ordered', overdue_date, 20
        )

        result = self.run_prediction([line], demand=0)

        self.assertEqual(result['overdue_incoming'], 20)
        self.assertEqual(result['unscheduled_incoming'], 0)
        self.assertEqual(
            result['daily_projection'][0]['incoming'],
            0
        )
        self.assertEqual(
            result['daily_projection'][0]['projected_stock'],
            20
        )

    def test_delivery_on_cutoff_date_is_overdue(self):
        line = self.make_line(
            'ordered', self.end_date, 10
        )

        result = self.run_prediction([line], demand=0)

        self.assertEqual(result['overdue_incoming'], 10)
        self.assertEqual(
            result['daily_projection'][0]['incoming'],
            0
        )

    def test_rejects_wrong_forecast_length(self):
        with patch(
            'intelligence.shortage_prediction.Product.objects.get',
            return_value=self.product
        ), patch(
            'intelligence.shortage_prediction.forecast_product_demand',
            return_value={'predictions': []}
        ):
            with self.assertRaisesRegex(
                ValueError, 'Expected 30 forecast days'
            ):
                predict_stock_shortage(30, self.end_date)

    def test_rejects_wrong_forecast_date(self):
        forecast = self.make_forecast()
        forecast['predictions'][0]['date'] = self.end_date

        with patch(
            'intelligence.shortage_prediction.Product.objects.get',
            return_value=self.product
        ), patch(
            'intelligence.shortage_prediction.forecast_product_demand',
            return_value=forecast
        ):
            with self.assertRaisesRegex(
                ValueError, 'Invalid forecast dates'
            ):
                predict_stock_shortage(30, self.end_date)

    def test_rejects_invalid_forecast_demand(self):
        for invalid in [-1, float('nan'), float('inf'), True]:
            forecast = self.make_forecast()
            forecast['predictions'][0]['p50'] = invalid

            with self.subTest(value=invalid):
                with patch(
                    'intelligence.shortage_prediction.Product.objects.get',
                    return_value=self.product
                ), patch(
                    'intelligence.shortage_prediction.forecast_product_demand',
                    return_value=forecast
                ):
                    with self.assertRaisesRegex(
                        ValueError, 'Invalid forecast demand'
                    ):
                        predict_stock_shortage(
                            30, self.end_date
                        )
