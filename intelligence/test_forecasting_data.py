from datetime import date, timedelta

from django.test import TestCase

from catalog.models import Product, Supplier

from .models import DailySales
from .forecasting_data import get_forecasting_data


class ForecastingDataTests(TestCase):

    def setUp(self):
        self.supplier = Supplier.objects.create(
            name='Forecast Supplier'
        )

        self.product = Product.objects.create(
            sku='FORECAST-001',
            name='Forecast Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price=50
        )

        self.end_date = date(2026, 11, 12)
        self.start_date = self.end_date - timedelta(days=59)

        for day in range(60):
            DailySales.objects.create(
                product=self.product,
                date=self.start_date + timedelta(days=day),
                units_sold=0 if day == 5 else day + 1,
                gross_revenue=0,
                source='imported' if day < 10 else 'recorded'
            )

    def test_returns_60_values(self):
        history = get_forecasting_data(
            self.product.pk, self.end_date
        )
        self.assertEqual(len(history), 60)
        self.assertEqual(history[0], 1)
        self.assertEqual(history[-1], 60)

    def test_preserves_zero_sales(self):
        history = get_forecasting_data(
            self.product.pk, self.end_date
        )
        self.assertEqual(history[5], 0)

    def test_rejects_missing_date(self):
        DailySales.objects.filter(
            product=self.product,
            date=self.start_date + timedelta(days=10)
        ).delete()

        with self.assertRaisesRegex(ValueError, 'Missing sales history'):
            get_forecasting_data(self.product.pk, self.end_date)

    def test_rejects_short_history(self):
        with self.assertRaises(ValueError):
            get_forecasting_data(
                self.product.pk, self.end_date, days=28
            )

    def test_accepts_mixed_sources(self):
        history = get_forecasting_data(
            self.product.pk, self.end_date
        )
        self.assertEqual(len(history), 60)

    def test_does_not_change_sales(self):
        before = list(
            DailySales.objects.filter(
                product=self.product
            ).values_list('date', 'units_sold', 'source')
        )

        get_forecasting_data(self.product.pk, self.end_date)

        after = list(
            DailySales.objects.filter(
                product=self.product
            ).values_list('date', 'units_sold', 'source')
        )

        self.assertEqual(before, after)
