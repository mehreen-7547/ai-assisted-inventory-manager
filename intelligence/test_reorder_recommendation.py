
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .reorder_recommendation import (
    calculate_fallback_demand,
    get_fallback_sales,
    recommend_reorder_quantity
)


class ReorderRecommendationTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 13)
        self.product = SimpleNamespace(
            id=30,
            name='Test Notebook',
            on_hand=20,
            safety_stock=10,
            lead_time_days=7
        )

    def make_forecast(self, demand=5):
        return {
            'history_days': 60,
            'predictions': [
                {
                    'date': self.end_date + timedelta(days=day),
                    'p50': demand
                }
                for day in range(1, 31)
            ]
        }

    def make_line(self, delivery_date, ordered, received=0):
        return SimpleNamespace(
            quantity_ordered=ordered,
            quantity_received=received,
            purchase_order=SimpleNamespace(
                expected_delivery_date=delivery_date
            )
        )

    def run_recommendation(
        self, demand=5, lines=None, ai_error=None
    ):
        with patch(
            'intelligence.reorder_recommendation.Product.objects.get',
            return_value=self.product
        ), patch(
            'intelligence.reorder_recommendation.forecast_product_demand'
        ) as forecast, patch(
            'intelligence.reorder_recommendation.PurchaseOrderLine.objects.filter'
        ) as filter_lines, patch(
            'intelligence.reorder_recommendation.calculate_fallback_demand'
        ) as fallback:

            filter_lines.return_value.select_related.return_value = (
                lines if lines is not None else []
            )

            if ai_error is None:
                forecast.return_value = self.make_forecast(demand)
            else:
                forecast.side_effect = ai_error
                fallback.return_value = {
                    'method': 'non_ai_fallback',
                    'history_days': 15,
                    'average_daily_demand': 6,
                    'lead_time_demand': 42
                }

            return recommend_reorder_quantity(
                self.product.id, self.end_date
            )

    def test_ai_reorder_quantity(self):
        result = self.run_recommendation()
        self.assertEqual(result['reorder_quantity'], 25)
        self.assertEqual(result['method'], 'ai_chronos')

    def test_no_reorder_when_stock_is_sufficient(self):
        self.product.on_hand = 100
        result = self.run_recommendation()
        self.assertEqual(result['reorder_quantity'], 0)

    def test_rounds_only_final_quantity(self):
        result = self.run_recommendation(demand=1.05)
        self.assertEqual(result['reorder_quantity'], 0)

        self.product.on_hand = 0
        result = self.run_recommendation(demand=1.05)
        self.assertEqual(result['reorder_quantity'], 18)

    def test_incoming_within_lead_time(self):
        line = self.make_line(
            self.end_date + timedelta(days=7), 12
        )
        result = self.run_recommendation(lines=[line])
        self.assertEqual(result['scheduled_incoming'], 12)
        self.assertEqual(result['reorder_quantity'], 13)

    def test_late_delivery_is_excluded(self):
        line = self.make_line(
            self.end_date + timedelta(days=8), 12
        )
        result = self.run_recommendation(lines=[line])
        self.assertEqual(result['later_incoming'], 12)
        self.assertEqual(result['reorder_quantity'], 25)

    def test_overdue_and_undated_are_excluded(self):
        lines = [
            self.make_line(self.end_date, 10),
            self.make_line(None, 8)
        ]
        result = self.run_recommendation(lines=lines)
        self.assertEqual(result['overdue_incoming'], 10)
        self.assertEqual(result['unscheduled_incoming'], 8)
        self.assertEqual(result['reorder_quantity'], 25)

    def test_partial_receipt_uses_remaining(self):
        line = self.make_line(
            self.end_date + timedelta(days=3),
            ordered=20,
            received=12
        )
        result = self.run_recommendation(lines=[line])
        self.assertEqual(result['scheduled_incoming'], 8)
        self.assertEqual(result['reorder_quantity'], 17)

    def test_ai_failure_uses_fallback(self):
        result = self.run_recommendation(
            ai_error=RuntimeError('Model unavailable')
        )
        self.assertEqual(result['method'], 'non_ai_fallback')
        self.assertEqual(result['reorder_quantity'], 32)
        self.assertIn('Model unavailable', result['ai_error'])

    def test_invalid_lead_time(self):
        self.product.lead_time_days = 31
        result = self.run_recommendation()
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['reorder_quantity'])

    def test_invalid_end_date(self):
        with self.assertRaisesRegex(ValueError, 'Invalid end date'):
            recommend_reorder_quantity(30, '2026-11-13')

    def test_invalid_forecast_uses_fallback(self):
        with patch(
            'intelligence.reorder_recommendation.Product.objects.get',
            return_value=self.product
        ), patch(
            'intelligence.reorder_recommendation.forecast_product_demand',
            return_value={'history_days': 60, 'predictions': []}
        ), patch(
            'intelligence.reorder_recommendation.PurchaseOrderLine.objects.filter'
        ) as filter_lines, patch(
            'intelligence.reorder_recommendation.calculate_fallback_demand',
            side_effect=ValueError('Not enough history')
        ):
            filter_lines.return_value.select_related.return_value = []

            result = recommend_reorder_quantity(
                30, self.end_date
            )

        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['reorder_quantity'])
        self.assertIn('Not enough history', result['reason'])


class ReorderFallbackTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 13)

    def make_records(self, quantities):
        return [
            SimpleNamespace(
                date=self.end_date - timedelta(days=index),
                units_sold=quantity
            )
            for index, quantity in enumerate(quantities)
        ]

    def test_average_includes_zero_sales(self):
        records = self.make_records([5, 0, 0, 7, 0, 3, 0])

        with patch(
            'intelligence.reorder_recommendation.DailySales.objects.filter'
        ) as filter_sales:
            filter_sales.return_value.order_by.return_value.__getitem__.return_value = records

            result = calculate_fallback_demand(
                30, self.end_date, 7
            )

        self.assertEqual(result['history_days'], 7)
        self.assertAlmostEqual(
            result['lead_time_demand'], 15
        )

    def test_missing_day_breaks_history(self):
        records = self.make_records([2] * 7)
        records[3].date -= timedelta(days=1)

        with patch(
            'intelligence.reorder_recommendation.DailySales.objects.filter'
        ) as filter_sales:
            filter_sales.return_value.order_by.return_value.__getitem__.return_value = records

            with self.assertRaisesRegex(
                ValueError, 'At least 7 consecutive days'
            ):
                get_fallback_sales(30, self.end_date)

    def test_fallback_requires_seven_days(self):
        records = self.make_records([2] * 6)

        with patch(
            'intelligence.reorder_recommendation.DailySales.objects.filter'
        ) as filter_sales:
            filter_sales.return_value.order_by.return_value.__getitem__.return_value = records

            with self.assertRaises(ValueError):
                get_fallback_sales(30, self.end_date)

    def test_fallback_rejects_invalid_lead_time(self):
        with self.assertRaisesRegex(
            ValueError, 'between 1 and 30 days'
        ):
            calculate_fallback_demand(
                30, self.end_date, 31
            )
