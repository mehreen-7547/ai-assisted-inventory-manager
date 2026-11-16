from django.utils import timezone
from catalog.models import Product
from intelligence.models import DailySales
from intelligence.reorder_recommendation import recommend_reorder_quantity, get_recent_average
from intelligence.shortage_prediction import predict_stock_shortage
from intelligence.anomaly_detection import detect_sales_anomalies


def get_needs_attention_today():
    items = []
    failures = 0
    for product in Product.objects.filter(is_active=True).order_by('sku'):
        last_date = (DailySales.objects.filter(product=product, date__lte=timezone.localdate())
                     .order_by('-date').values_list('date', flat=True).first())
        end_date = last_date or timezone.localdate()
        failed = False
        try:
            reorder = recommend_reorder_quantity(product.pk, end_date)
        except Exception:
            reorder = None
            failed = True
        try:
            shortage = predict_stock_shortage(product.pk, end_date)
        except Exception:
            shortage = None
            failed = True
        try:
            anomalies = detect_sales_anomalies(product.pk, end_date, days=7)
        except Exception:
            anomalies = None
            failed = True
        try:
            average = get_recent_average(product.pk, end_date)
        except Exception:
            average = None
            failed = True
        if failed:
            failures += 1

        quantity = (reorder or {}).get('reorder_quantity')
        if (reorder or {}).get('status') == 'available' and quantity is not None and quantity > 0:
            breach = (shortage or {}).get('first_stockout') or (shortage or {}).get('first_safety_breach')
            days_until = (breach - end_date).days if breach else 9999
            items.append({'product': product, 'kind': 'Reorder now',
                          'detail': f'Order {quantity} units',
                          'rank': (0, days_until, -quantity, product.sku)})
        elif average is not None and average > 0 and product.on_hand / average > 90:
            cover = round(product.on_hand / average)
            items.append({'product': product, 'kind': 'Overstocked',
                          'detail': f'About {cover} days of cover',
                          'rank': (1, -cover, 0, product.sku)})
        elif (anomalies or {}).get('anomaly_count', 0) > 0:
            count = anomalies['anomaly_count']
            items.append({'product': product, 'kind': 'Unusual sales',
                          'detail': f'{count} unusual day(s) in the last 7 days',
                          'rank': (2, -count, 0, product.sku)})
    items.sort(key=lambda item: item['rank'])
    return {'items': items[:10], 'failed_products': failures}
