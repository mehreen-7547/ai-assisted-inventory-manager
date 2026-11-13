from datetime import date, datetime, timedelta

from .models import DailySales


MIN_HISTORY_DAYS = 60


def get_forecasting_data(product_id, end_date, days=MIN_HISTORY_DAYS):

    if not isinstance(end_date, date) or isinstance(end_date, datetime):
        raise ValueError('Invalid end date')

    if type(days) is not int or days < MIN_HISTORY_DAYS:
        raise ValueError('At least 60 days of history are required')

    start_date = end_date - timedelta(days=days - 1)

    records = DailySales.objects.filter(
        product_id=product_id,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    sales_by_date = {
        record.date: record.units_sold
        for record in records
    }

    history = []
    current_date = start_date

    while current_date <= end_date:
        if current_date not in sales_by_date:
            raise ValueError(
                f'Missing sales history for {current_date}'
            )

        history.append(sales_by_date[current_date])
        current_date += timedelta(days=1)

    return history
