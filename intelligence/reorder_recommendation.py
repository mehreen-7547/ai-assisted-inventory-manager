
from datetime import date, datetime, timedelta
from math import ceil, isfinite

from django.db.models import F

from catalog.models import Product
from purchasing.models import PurchaseOrderLine

from .forecasting import forecast_product_demand
from .models import DailySales


def get_fallback_sales(product_id, end_date):
    records = list(
        DailySales.objects.filter(
            product_id=product_id,
            date__lte=end_date
        ).order_by('-date')[:59]
    )

    sales = []
    expected_date = end_date

    for record in records:
        if record.date != expected_date:
            break

        sales.append(record.units_sold)
        expected_date -= timedelta(days=1)

    if len(sales) < 7:
        raise ValueError(
            'At least 7 consecutive days of sales are required'
        )

    return sales


def calculate_fallback_demand(
    product_id, end_date, lead_time_days
):
    if type(lead_time_days) is not int or not 1 <= lead_time_days <= 30:
        raise ValueError(
            'Supplier lead time must be between 1 and 30 days'
        )

    sales = get_fallback_sales(product_id, end_date)

    average_daily_demand = sum(sales) / len(sales)

    return {
        'method': 'non_ai_fallback',
        'history_days': len(sales),
        'average_daily_demand': average_daily_demand,
        'lead_time_demand': (
            average_daily_demand * lead_time_days
        )
    }


def get_ai_lead_time_demand(
    product_id, end_date, lead_time_days
):
    forecast = forecast_product_demand(
        product_id, end_date
    )

    predictions = forecast['predictions']

    if len(predictions) != 30:
        raise ValueError('Expected 30 forecast days')

    total_demand = 0

    for day, prediction in enumerate(predictions, start=1):
        expected_date = end_date + timedelta(days=day)

        if prediction['date'] != expected_date:
            raise ValueError('Invalid forecast dates')

        demand = prediction['p50']

        if (
            not isinstance(demand, (int, float))
            or isinstance(demand, bool)
            or not isfinite(demand)
            or demand < 0
        ):
            raise ValueError('Invalid forecast demand')

        if day <= lead_time_days:
            total_demand += demand

    return {
        'method': 'ai_chronos',
        'history_days': forecast['history_days'],
        'average_daily_demand': None,
        'lead_time_demand': total_demand
    }


def get_incoming_stock(
    product_id, end_date, lead_time_days
):
    cutoff_date = end_date + timedelta(
        days=lead_time_days
    )

    lines = PurchaseOrderLine.objects.filter(
        product_id=product_id,
        purchase_order__status__in=[
            'ordered',
            'partially_received'
        ],
        quantity_ordered__gt=F('quantity_received')
    ).select_related('purchase_order')

    scheduled_incoming = 0
    overdue_incoming = 0
    unscheduled_incoming = 0
    later_incoming = 0

    for line in lines:
        remaining = (
            line.quantity_ordered - line.quantity_received
        )

        delivery_date = (
            line.purchase_order.expected_delivery_date
        )

        if delivery_date is None:
            unscheduled_incoming += remaining
        elif delivery_date <= end_date:
            overdue_incoming += remaining
        elif delivery_date <= cutoff_date:
            scheduled_incoming += remaining
        else:
            later_incoming += remaining

    return {
        'scheduled_incoming': scheduled_incoming,
        'overdue_incoming': overdue_incoming,
        'unscheduled_incoming': unscheduled_incoming,
        'later_incoming': later_incoming
    }


def recommend_reorder_quantity(product_id, end_date):
    if (
        not isinstance(end_date, date)
        or isinstance(end_date, datetime)
    ):
        raise ValueError('Invalid end date')

    product = Product.objects.get(id=product_id)

    lead_time_days = product.lead_time_days

    result = {
        'product_id': product.id,
        'product_name': product.name,
        'on_hand': product.on_hand,
        'safety_stock': product.safety_stock,
        'lead_time_days': lead_time_days,
        'status': 'unavailable',
        'method': None,
        'history_days': None,
        'average_daily_demand': None,
        'lead_time_demand': None,
        'scheduled_incoming': 0,
        'overdue_incoming': 0,
        'unscheduled_incoming': 0,
        'later_incoming': 0,
        'reorder_quantity': None,
        'reason': None,
        'ai_error': None
    }

    if type(lead_time_days) is not int or not 1 <= lead_time_days <= 30:
        result['reason'] = (
            'Supplier lead time must be between 1 and 30 days'
        )
        return result

    incoming = get_incoming_stock(
        product_id, end_date, lead_time_days
    )

    result.update(incoming)

    try:
        demand = get_ai_lead_time_demand(
            product_id, end_date, lead_time_days
        )
    except Exception as error:
        result['ai_error'] = str(error)

        try:
            demand = calculate_fallback_demand(
                product_id, end_date, lead_time_days
            )
        except (ValueError, TypeError) as fallback_error:
            result['reason'] = (
                'Unable to calculate reorder quantity: '
                + str(fallback_error)
            )
            return result

    result.update(demand)

    required_quantity = (
        demand['lead_time_demand']
        + product.safety_stock
        - product.on_hand
        - incoming['scheduled_incoming']
    )

    result['reorder_quantity'] = max(
        0, ceil(required_quantity)
    )

    result['status'] = 'available'

    if result['reorder_quantity'] == 0:
        result['reason'] = 'No reorder required'
    else:
        result['reason'] = 'Reorder recommended'

    return result
