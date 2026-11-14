
from datetime import date, datetime, timedelta
from math import isfinite

from .models import DailySales


BASELINE_DAYS = 14
DEFAULT_THRESHOLD_PERCENT = 50
DEFAULT_MINIMUM_DIFFERENCE = 5
DEFAULT_ANALYSIS_DAYS = 30


def detect_sales_anomalies(
    product_id,
    end_date,
    days=DEFAULT_ANALYSIS_DAYS,
    threshold_percent=DEFAULT_THRESHOLD_PERCENT,
    minimum_difference=DEFAULT_MINIMUM_DIFFERENCE
):
    if (
        not isinstance(end_date, date)
        or isinstance(end_date, datetime)
    ):
        raise ValueError('Invalid end date')

    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError(
            'Analysis days must be between 1 and 30'
        )

    if (
        not isinstance(threshold_percent, (int, float))
        or isinstance(threshold_percent, bool)
        or not isfinite(threshold_percent)
        or threshold_percent <= 0
    ):
        raise ValueError('Invalid percentage threshold')

    if (
        type(minimum_difference) is not int
        or minimum_difference < 1
    ):
        raise ValueError('Invalid minimum difference')

    start_date = end_date - timedelta(days=days - 1)
    history_start = start_date - timedelta(
        days=BASELINE_DAYS
    )

    records = DailySales.objects.filter(
        product_id=product_id,
        date__gte=history_start,
        date__lte=end_date
    ).order_by('date')

    sales_by_date = {
        record.date: record.units_sold
        for record in records
    }

    anomalies = []
    skipped_days = []
    analyzed_days = 0

    for day_number in range(days):
        current_date = start_date + timedelta(
            days=day_number
        )

        actual_sales = sales_by_date.get(current_date)

        if actual_sales is None:
            skipped_days.append({
                'date': current_date,
                'reason': 'Missing daily sales record'
            })
            continue

        history = []
        missing_history = False

        for previous_day in range(
            BASELINE_DAYS, 0, -1
        ):
            history_date = current_date - timedelta(
                days=previous_day
            )

            if history_date not in sales_by_date:
                missing_history = True
                break

            history.append(
                sales_by_date[history_date]
            )

        if missing_history:
            skipped_days.append({
                'date': current_date,
                'reason': 'Incomplete 14-day sales history'
            })
            continue

        analyzed_days += 1

        average_sales = sum(history) / BASELINE_DAYS

        difference = actual_sales - average_sales
        absolute_difference = abs(difference)

        if average_sales == 0:
            percentage_change = None

            is_anomaly = (
                absolute_difference
                >= minimum_difference
            )
        else:
            percentage_change = (
                difference / average_sales
            ) * 100

            is_anomaly = (
                absolute_difference >= minimum_difference
                and abs(percentage_change)
                >= threshold_percent
            )

        if not is_anomaly:
            continue

        if difference > 0:
            anomaly_type = 'unusually_high'
            explanation = (
                'Sales are unusually high compared '
                'with the previous 14 days'
            )
        else:
            anomaly_type = 'unusually_low'
            explanation = (
                'Sales are unusually low compared '
                'with the previous 14 days'
            )

        anomalies.append({
            'date': current_date,
            'actual_sales': actual_sales,
            'average_sales': round(average_sales, 2),
            'difference': round(difference, 2),
            'percentage_change': (
                round(percentage_change, 2)
                if percentage_change is not None
                else None
            ),
            'anomaly_type': anomaly_type,
            'explanation': explanation
        })

    return {
        'product_id': product_id,
        'start_date': start_date,
        'end_date': end_date,
        'baseline_days': BASELINE_DAYS,
        'threshold_percent': threshold_percent,
        'minimum_difference': minimum_difference,
        'analyzed_days': analyzed_days,
        'skipped_days': skipped_days,
        'anomaly_count': len(anomalies),
        'anomalies': anomalies,
        'method': 'statistical_rolling_average'
    }
