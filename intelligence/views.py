import math
from datetime import date, timedelta
from math import ceil

from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from catalog.models import Product

from .forecasting import forecast_product_demand
from .shortage_prediction import predict_stock_shortage
from .reorder_recommendation import recommend_reorder_quantity
from .anomaly_detection import detect_sales_anomalies
from .models import DailySales
from .forecast_evaluation import evaluate_product_forecast
from .reorder_recommendation import get_recent_average




def whole_units(value):
    """Round estimated item counts to the nearest whole unit (half up)."""
    return int(math.floor(float(value) + 0.5))


def item_label(n):
    return f"{n} {'unit' if n == 1 else 'units'}"


def selling_display(average):
    if average is None or average < 0:
        return {'main': 'Unavailable', 'note': 'Not enough sales history', 'rate': None}
    if average == 0:
        return {'main': 'No recent sales', 'note': 'Based on the last 4 weeks', 'rate': None}
    if average < 1:
        main = f'About {whole_units(average * 7)} a week'
        rate = f'{whole_units(average * 7)} a week'
    else:
        main = f'About {whole_units(average)} a day'
        rate = f'{whole_units(average)} a day'
    return {'main': main, 'note': 'Based on the last 4 weeks', 'rate': rate,
            'slow_note': f'Roughly 1 every {whole_units(1 / average)} days' if average < 0.5 else None}


def build_decision_summary(product, insight, results, evaluation, analysis_date=None):
    average = insight.get('recent_daily_average')
    cover = insight.get('days_of_cover')
    reorder = results.get('reorder') or {}
    shortage = results.get('shortage') or {}
    forecast = results.get('forecast') or {}
    quantity = reorder.get('reorder_quantity') if reorder.get('status') == 'available' else None
    selling = selling_display(average)
    days = whole_units(cover) if cover is not None else None
    months = whole_units(cover / 30.44) if cover is not None and cover > 60 else None
    if cover is not None and cover > 90:
        verdict, tone = 'Overstocked', 'warning'
        headline = (f'No reorder needed. Your stock will last about {days} days.' if quantity == 0
                    else f'Your stock could last about {days} days. Review the reorder advice.')
    elif quantity is not None and quantity > 0:
        verdict, tone = 'Reorder now', 'danger'
        headline = f'Consider ordering {item_label(quantity)} to protect your minimum stock.'
    elif quantity == 0:
        verdict, tone = 'Stock is healthy', 'success'
        headline = 'No reorder needed right now.'
    else:
        verdict, tone = 'Review needed', 'secondary'
        headline = 'Reorder advice is unavailable.'
    support = f'You have {item_label(product.on_hand)}.'
    if selling['rate']:
        support = f'You have {item_label(product.on_hand)} and sell about {selling["rate"]}.'
    if months is not None:
        support += f' At this pace it would take about {months} months to sell them.'
    next_14 = average * 14 if average is not None else None
    predictions = forecast.get('predictions') or []
    ai_14 = sum(day['p50'] for day in predictions[:14]) if len(predictions) >= 14 else None
    lead_demand = reorder.get('lead_time_demand') if reorder.get('status') == 'available' else None
    if shortage:
        stockout = shortage.get('first_stockout')
        breach = shortage.get('first_safety_breach')
        if isinstance(stockout, date):
            remaining = (stockout - analysis_date).days if isinstance(analysis_date, date) else None
            shortage_message = f'You may run out on {stockout:%d %b %Y}.'
            if remaining is not None:
                shortage_message += f' That is in {remaining} days.'
            shortage_message += ' Reorder soon.'
        elif isinstance(breach, date):
            shortage_message = f'Stock may fall below your minimum of {product.safety_stock} on {breach:%d %b %Y}.'
        else:
            shortage_message = 'No shortage expected in the next 30 days.'
    else:
        shortage_message = 'Shortage information is unavailable.'
    if evaluation:
        ai_error = evaluation.get('ai_total_error')
        baseline_error = evaluation.get('baseline_total_error')
        if ai_error is None or baseline_error is None:
            winner = None
        elif ai_error < baseline_error:
            winner = 'On this product the AI model came closer.'
        elif baseline_error < ai_error:
            winner = 'On this product the simple average came closer.'
        else:
            winner = 'On this product both methods were equally close.'
    else:
        winner = None
    incoming = shortage if shortage else reorder
    incoming_sentences = []
    if incoming:
        # The shortage service includes all dated incoming stock, not just lead-time orders.
        dated = incoming.get('incoming_orders')
        if dated:
            for row in dated:
                incoming_sentences.append(f"{item_label(row['quantity'])} on order, arriving {row['date']:%d %b %Y}.")
        overdue = incoming.get('overdue_orders')
        if overdue:
            for row in overdue:
                incoming_sentences.append(f"{item_label(row['quantity'])} overdue: expected {row['date']:%d %b %Y}, not received.")
        elif incoming.get('overdue_incoming'):
            incoming_sentences.append(f"{item_label(incoming['overdue_incoming'])} overdue.")
        if incoming.get('unscheduled_incoming'):
            incoming_sentences.append(f"{item_label(incoming['unscheduled_incoming'])} on order with no delivery date.")
        if not dated and incoming.get('scheduled_incoming'):
            incoming_sentences.append(f"{item_label(incoming['scheduled_incoming'])} on order.")
        if not dated and incoming.get('later_incoming'):
            incoming_sentences.append(f"{item_label(incoming['later_incoming'])} on order for a later date.")
    incoming_message = ' '.join(incoming_sentences) if incoming_sentences else ('Nothing on order.' if incoming else 'Order information is unavailable.')
    anomalies = results.get('anomalies') or {}
    unusual_messages = []
    for row in anomalies.get('anomalies') or []:
        direction = 'far more' if row.get('anomaly_type') == 'unusually_high' else 'far less'
        unusual_messages.append(f"{row['date']:%d %b}: sold {item_label(row['actual_sales'])}, {direction} than normal.")
    unusual_message = ' '.join(unusual_messages) if unusual_messages else ('No unusual days in the last 30 days.' if anomalies else 'Sales information is unavailable.')
    return {
        'verdict': verdict, 'headline': headline, 'tone': tone, 'support': support,
        'on_hand_label': item_label(product.on_hand),
        'reorder_label': item_label(quantity) if quantity is not None else None,
        'average': average, 'cover': cover, 'cover_whole': days,
        'selling': selling, 'next_14': next_14, 'ai_14': ai_14,
        'next_14_whole': whole_units(next_14) if next_14 is not None else None,
        'ai_14_whole': whole_units(ai_14) if ai_14 is not None else None,
        'reorder_quantity': quantity,
        'lead_time_demand_whole': whole_units(lead_demand) if lead_demand is not None else None,
        'shortage_message': shortage_message, 'incoming_message': incoming_message,
        'unusual_message': unusual_message, 'accuracy_winner': winner,
    }


@role_required('manager')
def intelligence_dashboard(request):
    products = Product.objects.filter(
        is_active=True
    ).order_by('name')

    selected_product = None
    results = {}
    errors = {}
    analysis_date = None
    insight = {}
    weekly_forecast = []
    evaluation = None
    evaluation_error = None
    decision = None

    product_id = request.GET.get('product')

    if product_id:
        selected_product = products.filter(
            pk=product_id
        ).first() if product_id.isdigit() else None

        if selected_product is None:
            errors['selection'] = (
                'Please select a valid active product.'
            )
        else:
            latest_sales_date = DailySales.objects.filter(
                product=selected_product,
                date__lte=timezone.localdate()
            ).order_by('-date').values_list('date', flat=True).first()

            end_date = latest_sales_date or timezone.localdate()
            analysis_date = end_date

            services = {
                'forecast': forecast_product_demand,
                'shortage': predict_stock_shortage,
                'reorder': recommend_reorder_quantity,
                'anomalies': detect_sales_anomalies
            }

            for name, service in services.items():
                try:
                    results[name] = service(
                        selected_product.pk,
                        end_date
                    )
                except Exception:
                    errors[name] = (
                        'This analysis is currently unavailable.'
                    )

    if selected_product and analysis_date:
        average = get_recent_average(selected_product.pk, analysis_date)
        insight['recent_daily_average'] = average
        insight['days_of_cover'] = (
            round(selected_product.on_hand / average, 1)
            if average is not None and average > 0 else None
        )
        insight['overstocked'] = (
            insight['days_of_cover'] is not None
            and insight['days_of_cover'] > 90
        )
        if average == 0:
            insight['cover_message'] = 'No sales in the last 28 days; days of cover cannot be estimated.'
        elif average is None:
            insight['cover_message'] = '28 consecutive sales records required for days of cover.'
        else:
            insight['cover_message'] = None

        forecast = results.get('forecast')
        if forecast:
            predictions = forecast['predictions']
            insight['next_14_day_median_total'] = round(
                sum(row['p50'] for row in predictions[:14]), 2
            )
            for start in range(0, len(predictions), 7):
                segment = predictions[start:start + 7]
                weekly_forecast.append({
                    'start': segment[0]['date'],
                    'end': segment[-1]['date'],
                    'days': len(segment),
                    'median_total': round(sum(row['p50'] for row in segment), 2)
                })
        try:
            evaluation = evaluate_product_forecast(
                selected_product.pk, analysis_date
            )
        except (ValueError, TypeError, RuntimeError, OSError) as error:
            evaluation_error = 'Historical accuracy is unavailable for this product.'

    if selected_product:
        decision = build_decision_summary(
            selected_product, insight, results, evaluation, analysis_date
        )

    return render(
        request,
        'intelligence/dashboard.html',
        {
            'products': products,
            'selected_product': selected_product,
            'results': results,
            'errors': errors,
            'analysis_date': analysis_date,
            'insight': insight,
            'weekly_forecast': weekly_forecast,
            'evaluation': evaluation,
            'evaluation_error': evaluation_error,
            'decision': decision
        }
    )
