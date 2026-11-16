from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from django.template.loader import get_template
from .views import build_decision_summary, selling_display, item_label
from .shortage_prediction import predict_stock_shortage

class FinalWordingTests(SimpleTestCase):
    def setUp(self):
        self.product = SimpleNamespace(id=1, name='Test', on_hand=131, safety_stock=24, lead_time_days=2)
        self.insight = {'recent_daily_average': 20 / 28, 'days_of_cover': 193}
        self.results = {'reorder': {'status': 'available', 'reorder_quantity': 0},
                        'shortage': {'first_stockout': None, 'first_safety_breach': None,
                                    'incoming_orders': [], 'overdue_orders': [], 'unscheduled_incoming': 0},
                        'anomalies': {'anomalies': [], 'anomaly_count': 0}}

    def summary(self):
        return build_decision_summary(self.product, self.insight, self.results, None, date(2026, 11, 13))

    def test_selling_whole_units(self):
        self.assertEqual(selling_display(.26)['main'], 'About 2 a week')
        self.assertEqual(selling_display(.68)['main'], 'About 5 a week')
        self.assertEqual(selling_display(4.2)['main'], 'About 4 a day')
        self.assertEqual(selling_display(.26)['slow_note'], 'Roughly 1 every 4 days')

    def test_singular(self):
        self.assertEqual(item_label(1), '1 unit')
        self.assertEqual(item_label(2), '2 units')

    def test_verdict_and_no_shortage(self):
        s = self.summary()
        self.assertEqual(s['headline'], 'No reorder needed. Your stock will last about 193 days.')
        self.assertIn('sell about 5 a week', s['support'])
        self.assertNotIn('about About', s['support'])
        self.assertEqual(s['shortage_message'], 'No shortage expected in the next 30 days.')

    def test_stockout_and_safety_breach(self):
        self.results['shortage']['first_stockout'] = date(2026, 11, 22)
        self.assertIn('in 9 days', self.summary()['shortage_message'])
        self.results['shortage']['first_stockout'] = None
        self.results['shortage']['first_safety_breach'] = date(2026, 11, 20)
        self.assertIn('minimum of 24', self.summary()['shortage_message'])

    def test_incoming_variants(self):
        self.assertEqual(self.summary()['incoming_message'], 'Nothing on order.')
        self.results['shortage']['incoming_orders'] = [{'quantity': 50, 'date': date(2026, 11, 20)}]
        self.results['shortage']['overdue_orders'] = [{'quantity': 30, 'date': date(2026, 11, 10)}]
        self.results['shortage']['unscheduled_incoming'] = 20
        message = self.summary()['incoming_message']
        for phrase in ('50 units on order, arriving 20 Nov 2026.',
                       '30 units overdue: expected 10 Nov 2026, not received.',
                       '20 units on order with no delivery date.'):
            self.assertIn(phrase, message)

    def test_unusual_sales(self):
        self.assertEqual(self.summary()['unusual_message'], 'No unusual days in the last 30 days.')
        self.results['anomalies']['anomalies'] = [{'date': date(2026, 11, 3),
            'actual_sales': 14, 'anomaly_type': 'unusually_high'}]
        self.assertIn('3 Nov: sold 14 units, far more than normal.', self.summary()['unusual_message'])

    def test_no_banned_words_in_visible_template(self):
        source = get_template('intelligence/dashboard.html').template.source
        before = source.split('<summary class="text-primary">How is this calculated?</summary>')[0]
        for phrase in ('typical-day', 'recent_28_day_average', 'ai_chronos', 'selling about {{ decision.selling.main }}'):
            self.assertNotIn(phrase, before)

    @patch('intelligence.shortage_prediction.get_recent_average', return_value=2)
    @patch('intelligence.shortage_prediction.PurchaseOrderLine.objects.filter')
    @patch('intelligence.shortage_prediction.forecast_product_demand')
    @patch('intelligence.shortage_prediction.Product.objects.get')
    def test_shortage_uses_higher_demand(self, get_product, forecast, lines, average):
        get_product.return_value = SimpleNamespace(id=1, name='Test', on_hand=10, safety_stock=3, lead_time_days=2)
        end = date(2026, 11, 13)
        forecast.return_value = {'predictions': [
            {'date': end + timedelta(days=i), 'p50': .1} for i in range(1, 31)]}
        lines.return_value.select_related.return_value = []
        result = predict_stock_shortage(1, end)
        self.assertEqual(result['daily_projection'][0]['predicted_demand'], 2)
        self.assertEqual(result['first_safety_breach'], end + timedelta(days=4))
        self.assertEqual(result['first_stockout'], end + timedelta(days=6))
