
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .anomaly_detection import detect_sales_anomalies


class SalesAnomalyDetectionTests(SimpleTestCase):

    def setUp(self):
        self.end_date = date(2026, 11, 13)
        self.product_id = 30

    def make_records(self, quantities):
        start_date = self.end_date - timedelta(
            days=len(quantities) - 1
        )

        return [
            SimpleNamespace(
                date=start_date + timedelta(days=index),
                units_sold=quantity
            )
            for index, quantity in enumerate(quantities)
        ]

    def run_detection(self, quantities, days=1, **kwargs):
        records = self.make_records(quantities)

        with patch(
            'intelligence.anomaly_detection.DailySales.objects.filter'
        ) as filter_sales:

            filter_sales.return_value.order_by.return_value = (
                records
            )

            return detect_sales_anomalies(
                self.product_id,
                self.end_date,
                days=days,
                **kwargs
            )

    def test_unusually_high_sales(self):
        result = self.run_detection([10] * 14 + [20])

        self.assertEqual(result['anomaly_count'], 1)
        self.assertEqual(
            result['anomalies'][0]['anomaly_type'],
            'unusually_high'
        )
        self.assertEqual(
            result['anomalies'][0]['percentage_change'],
            100
        )

    def test_unusually_low_sales(self):
        result = self.run_detection([20] * 14 + [5])

        self.assertEqual(result['anomaly_count'], 1)
        self.assertEqual(
            result['anomalies'][0]['anomaly_type'],
            'unusually_low'
        )

    def test_normal_sales_not_flagged(self):
        result = self.run_detection([10] * 14 + [12])

        self.assertEqual(result['anomaly_count'], 0)
        self.assertEqual(result['analyzed_days'], 1)

    def test_small_percentage_spike_not_flagged(self):
        result = self.run_detection([1] * 14 + [3])

        self.assertEqual(result['anomaly_count'], 0)

    def test_percentage_threshold_required(self):
        result = self.run_detection([20] * 14 + [26])

        self.assertEqual(result['anomaly_count'], 0)

    def test_zero_baseline_with_large_spike(self):
        result = self.run_detection([0] * 14 + [8])

        self.assertEqual(result['anomaly_count'], 1)
        self.assertIsNone(
            result['anomalies'][0]['percentage_change']
        )

    def test_zero_baseline_with_small_spike(self):
        result = self.run_detection([0] * 14 + [3])

        self.assertEqual(result['anomaly_count'], 0)

    def test_zero_baseline_and_zero_actual(self):
        result = self.run_detection([0] * 15)

        self.assertEqual(result['anomaly_count'], 0)

    def test_recorded_zero_sales_is_valid(self):
        result = self.run_detection([10] * 14 + [0])

        self.assertEqual(result['anomaly_count'], 1)
        self.assertEqual(result['analyzed_days'], 1)

    def test_missing_history_is_skipped(self):
        records = self.make_records([10] * 14 + [20])
        del records[5]

        with patch(
            'intelligence.anomaly_detection.DailySales.objects.filter'
        ) as filter_sales:
            filter_sales.return_value.order_by.return_value = (
                records
            )

            result = detect_sales_anomalies(
                self.product_id, self.end_date, days=1
            )

        self.assertEqual(result['analyzed_days'], 0)
        self.assertEqual(len(result['skipped_days']), 1)

    def test_missing_target_day_is_skipped(self):
        result = self.run_detection([10] * 14)

        self.assertEqual(result['analyzed_days'], 0)
        self.assertEqual(result['anomaly_count'], 0)

    def test_rolling_baseline_updates_each_day(self):
        result = self.run_detection(
            [10] * 14 + [30, 30],
            days=2
        )

        self.assertEqual(result['anomaly_count'], 2)
        self.assertGreater(
            result['anomalies'][1]['average_sales'],
            result['anomalies'][0]['average_sales']
        )

    def test_custom_thresholds(self):
        result = self.run_detection(
            [10] * 14 + [14],
            threshold_percent=30,
            minimum_difference=3
        )

        self.assertEqual(result['anomaly_count'], 1)

    def test_invalid_end_date(self):
        with self.assertRaisesRegex(
            ValueError, 'Invalid end date'
        ):
            detect_sales_anomalies(
                self.product_id, '2026-11-13'
            )

    def test_invalid_analysis_days(self):
        for days in [0, 31, True]:
            with self.subTest(days=days):
                with self.assertRaises(ValueError):
                    detect_sales_anomalies(
                        self.product_id,
                        self.end_date,
                        days=days
                    )

    def test_invalid_percentage_threshold(self):
        for threshold in [0, -10, float('nan'), True]:
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    detect_sales_anomalies(
                        self.product_id,
                        self.end_date,
                        threshold_percent=threshold
                    )

    def test_invalid_minimum_difference(self):
        for difference in [0, -1, 2.5, True]:
            with self.subTest(difference=difference):
                with self.assertRaises(ValueError):
                    detect_sales_anomalies(
                        self.product_id,
                        self.end_date,
                        minimum_difference=difference
                    )
