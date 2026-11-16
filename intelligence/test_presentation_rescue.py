from types import SimpleNamespace
from django.test import SimpleTestCase
from django.template.loader import get_template
from .views import build_decision_summary


class PresentationRescueTests(SimpleTestCase):
    def setUp(self):
        self.product = SimpleNamespace(on_hand=120, safety_stock=20)
        self.insight = {'recent_daily_average': 1, 'days_of_cover': 120}
        self.results = {'reorder': {'status': 'available', 'reorder_quantity': 0},
                        'shortage': {'first_stockout': None, 'first_safety_breach': None}}

    def test_overstocked_verdict(self):
        result = build_decision_summary(self.product, self.insight, self.results, None)
        self.assertEqual(result['verdict'], 'Overstocked')
        self.assertIn('No reorder needed', result['headline'])

    def test_reorder_now_verdict(self):
        self.insight['days_of_cover'] = 5
        self.results['reorder']['reorder_quantity'] = 12
        result = build_decision_summary(self.product, self.insight, self.results, None)
        self.assertEqual(result['verdict'], 'Reorder now')
        self.assertIn('12 units', result['headline'])

    def test_healthy_verdict(self):
        self.insight['days_of_cover'] = 45
        result = build_decision_summary(self.product, self.insight, self.results, None)
        self.assertEqual(result['verdict'], 'Stock is healthy')

    def test_unavailable_reorder_not_called_healthy(self):
        self.results['reorder'] = {'status': 'unavailable', 'reorder_quantity': None}
        result = build_decision_summary(self.product, self.insight, self.results, None)
        self.assertEqual(result['verdict'], 'Overstocked')
        self.assertNotIn('No reorder needed', result['headline'])

    def test_raw_methods_only_in_calculation_details(self):
        source = get_template('intelligence/dashboard.html').template.source
        before, after = source.split('<summary class="text-primary">How is this calculated?</summary>', 1)
        for token in ('ai_chronos', 'recent_28_day_average'):
            self.assertNotIn(token, before)
        self.assertNotIn('>p50<', before)
        self.assertIn('recent_28_day_average', after)

    def test_selling_display_examples(self):
        from .views import selling_display
        examples = [
            (0.26, 'About 2 a week', 'Based on the last 4 weeks'),
            (0.68, 'About 5 a week', 'Based on the last 4 weeks'),
            (1.5, 'About 2 a day', 'Based on the last 4 weeks'),
            (4.2, 'About 4 a day', 'Based on the last 4 weeks'),
        ]
        for rate, main, note in examples:
            with self.subTest(rate=rate):
                result = selling_display(rate)
                self.assertEqual(result['main'], main)
                self.assertEqual(result['note'], note)

    def test_selling_display_missing_and_zero(self):
        from .views import selling_display
        self.assertEqual(selling_display(None)['main'], 'Unavailable')
        self.assertEqual(selling_display(0)['main'], 'No recent sales')

    def test_selling_tile_uses_preformatted_values(self):
        source = get_template('intelligence/dashboard.html').template.source
        self.assertIn('{{ decision.selling.main }}', source)
        self.assertIn('{{ decision.selling.note }}', source)
        self.assertNotIn('{{ decision.average|floatformat:1 }}', source)

    def test_daily_forecast_is_collapsed(self):
        source = get_template('intelligence/dashboard.html').template.source
        self.assertIn('<details class="mt-3"><summary class="text-primary">Show daily forecast (30 days)</summary>', source)
