from datetime import timedelta
from math import isfinite

from django.db.models import F

from catalog.models import Product
from purchasing.models import PurchaseOrderLine

from .forecasting import forecast_product_demand


def predict_stock_shortage(product_id, end_date):

    product = Product.objects.get(id=product_id)

    forecast = forecast_product_demand(
        product_id,
        end_date
    )

    predictions = forecast['predictions']

    if len(predictions) != 30:
        raise ValueError('Expected 30 forecast days')

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

    incoming_lines = PurchaseOrderLine.objects.filter(
        product_id=product_id,
        purchase_order__status__in=[
            'ordered',
            'partially_received'
        ],
        quantity_ordered__gt=F('quantity_received')
    ).select_related('purchase_order')

    incoming_by_date = {}
    unscheduled_incoming = 0
    overdue_incoming = 0

    for line in incoming_lines:
        remaining = (
            line.quantity_ordered - line.quantity_received
        )

        delivery_date = (
            line.purchase_order.expected_delivery_date
        )

        if delivery_date is None:
            unscheduled_incoming += remaining
            continue

        if delivery_date <= end_date:
            overdue_incoming += remaining
            continue

        incoming_by_date[delivery_date] = (
            incoming_by_date.get(delivery_date, 0)
            + remaining
        )

    projected_stock = float(product.on_hand)

    first_safety_breach = None
    first_stockout = None

    daily_projection = []

    for prediction in predictions:
        date = prediction['date']
        demand = prediction['p50']

        incoming = incoming_by_date.get(date, 0)

        projected_stock += incoming
        projected_stock -= demand

        if (
            first_safety_breach is None
            and projected_stock < product.safety_stock
        ):
            first_safety_breach = date

        if (
            first_stockout is None
            and projected_stock < 0
        ):
            first_stockout = date

        daily_projection.append({
            'date': date,
            'predicted_demand': demand,
            'incoming': incoming,
            'projected_stock': round(projected_stock, 2)
        })

    return {
        'product_id': product.id,
        'product_name': product.name,
        'on_hand': product.on_hand,
        'safety_stock': product.safety_stock,
        'lead_time_days': product.lead_time_days,
        'unscheduled_incoming': unscheduled_incoming,
        'overdue_incoming': overdue_incoming,
        'first_safety_breach': first_safety_breach,
        'first_stockout': first_stockout,
        'daily_projection': daily_projection
    }
