
from datetime import timedelta
from math import isfinite

from catalog.models import Product
from .forecasting import forecast_product_demand
from .forecasting_data import get_forecasting_data


WEEKS = 8
WEEK_DAYS = 7
HISTORY_DAYS = 60


def evaluate_weekly_forecasts(end_date):
    """Compare weekly totals without using future sales for predictions."""
    products = Product.objects.order_by('pk')
    rows = []
    skipped = 0

    for product in products:
        for weeks_ago in range(WEEKS - 1, -1, -1):
            week_end = end_date - timedelta(days=weeks_ago * WEEK_DAYS)
            cutoff = week_end - timedelta(days=WEEK_DAYS)
            week_start = cutoff + timedelta(days=1)

            try:
                sales = get_forecasting_data(
                    product.pk, week_end, days=HISTORY_DAYS + WEEK_DAYS
                )
                history = sales[:HISTORY_DAYS]
                actual = sales[HISTORY_DAYS:]

                forecast = forecast_product_demand(product.pk, cutoff)
                predictions = forecast['predictions'][:WEEK_DAYS]

                if len(predictions) != WEEK_DAYS:
                    raise ValueError('Expected seven AI predictions')

                for day, prediction in enumerate(predictions, start=1):
                    if prediction['date'] != cutoff + timedelta(days=day):
                        raise ValueError('AI prediction dates do not match')

                ai_values = [float(p['p50']) for p in predictions]

                if not all(isfinite(v) and v >= 0 for v in ai_values):
                    raise ValueError('Invalid AI predictions')

            except (ValueError, TypeError, KeyError, RuntimeError,
                    OSError, ImportError):
                skipped += 1
                continue

            actual_total = sum(actual)
            ai_total = sum(ai_values)
            average_total = sum(history[-WEEK_DAYS:])

            rows.append({
                'product_id': product.pk,
                'product_name': product.name,
                'week_start': week_start,
                'week_end': week_end,
                'actual': actual_total,
                'ai': round(ai_total, 2),
                'average': average_total,
                'zero': 0,
                'ai_error': round(abs(actual_total - ai_total), 2),
                'average_error': abs(actual_total - average_total),
                'zero_error': actual_total,
            })

    count = len(rows)
    methods = ('ai', 'average', 'zero')

    totals = {
        method: round(sum(row[method + '_error'] for row in rows), 2)
        for method in methods
    }

    mean_errors = {
        method: round(totals[method] / count, 2) if count else None
        for method in methods
    }

    winners = (
        [method for method in methods
         if totals[method] == min(totals.values())]
        if count else []
    )

    return {
        'rows': rows,
        'product_count': products.count(),
        'evaluated_product_weeks': count,
        'skipped_product_weeks': skipped,
        'total_absolute_errors': totals,
        'mean_weekly_absolute_errors': mean_errors,
        'best_methods': winners,
        'weeks': WEEKS,
    }
