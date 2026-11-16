from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from core.attention import get_needs_attention_today


class NeedsAttentionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            username='attention_manager', email='attention@example.com',
            password='TestPassword123!', role='manager'
        )
        self.sales = User.objects.create_user(
            username='attention_sales', email='sales_attention@example.com',
            password='TestPassword123!', role='sales'
        )
        supplier = Supplier.objects.create(name='Attention Supplier')
        self.products = [Product.objects.create(
            sku=f'ATT-{i:03d}', name=f'Attention Product {i}',
            category='Test', supplier=supplier, unit_price=Decimal('10.00'),
            lead_time_days=7, safety_stock=5
        ) for i in range(12)]

    @patch('core.attention.get_recent_average', return_value=1)
    @patch('core.attention.detect_sales_anomalies', return_value={'anomaly_count': 0})
    @patch('core.attention.predict_stock_shortage', return_value={})
    @patch('core.attention.recommend_reorder_quantity')
    def test_ranked_top_ten_and_links(self, reorder, shortage, anomalies, average):
        reorder.side_effect = lambda pk, date: {
            'status': 'available', 'reorder_quantity': pk
        }
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        rows = response.context['needs_attention']['items']
        self.assertEqual(len(rows), 10)
        self.assertEqual([x['product'].pk for x in rows],
                         sorted([p.pk for p in self.products], reverse=True)[:10])
        self.assertContains(response, '?product=', count=10)

    @patch('core.attention.get_recent_average', return_value=1)
    @patch('core.attention.detect_sales_anomalies', return_value={'anomaly_count': 1})
    @patch('core.attention.predict_stock_shortage', return_value={})
    @patch('core.attention.recommend_reorder_quantity')
    def test_failure_does_not_break_panel(self, reorder, shortage, anomalies, average):
        reorder.side_effect = ValueError('forecast unavailable')
        self.products[0].on_hand = 200
        self.products[0].save(update_fields=['on_hand'])
        result = get_needs_attention_today()
        self.assertEqual(len(result['items']), 10)
        self.assertEqual(result['items'][0]['kind'], 'Overstocked')
        self.assertEqual(result['failed_products'], 12)

    @patch('core.views.get_needs_attention_today')
    def test_sales_user_does_not_run_attention(self, attention):
        self.client.force_login(self.sales)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        attention.assert_not_called()

    @patch('core.attention.get_recent_average', return_value=1)
    @patch('core.attention.detect_sales_anomalies', return_value={'anomaly_count': 0})
    @patch('core.attention.predict_stock_shortage', return_value={})
    @patch('core.attention.recommend_reorder_quantity', return_value={
        'status': 'available', 'reorder_quantity': 0
    })
    def test_empty_panel(self, reorder, shortage, anomalies, average):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'No attention items found from available data.')
