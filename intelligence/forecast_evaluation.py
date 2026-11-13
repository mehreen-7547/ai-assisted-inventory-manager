from datetime import timedelta
from math import isfinite

from .forecasting import forecast_product_demand
from .forecasting_data import get_forecasting_data


HISTORY_DAYS = 60
TEST_DAYS = 30
BASELINE_DAYS = 7


def calculate_mae(actual, predicted):

    if len(actual) != len(predicted) or not actual:
        raise ValueError('Invalid evaluation sequences')

    if not all(
        isfinite(value) and value >= 0
        for value in actual + predicted
    ):
        raise ValueError('Invalid evaluation values')

    errors = [
        abs(a - p)
        for a, p in zip(actual, predicted)
    ]

    return round(sum(errors) / len(errors), 4)


def evaluate_product_forecast(product_id, end_date):

    # Read 90 consecutive days, ending on the evaluation date.
    sales = get_forecasting_data(
        product_id,
        end_date,
        days=HISTORY_DAYS + TEST_DAYS
    )

    history = sales[:HISTORY_DAYS]
    actual = sales[HISTORY_DAYS:]

    # The model must only see data before the test period.
    cutoff_date = end_date - timedelta(days=TEST_DAYS)

    forecast = forecast_product_demand(
        product_id,
        cutoff_date
    )

    predictions = forecast['predictions']

    if len(predictions) != TEST_DAYS:
        raise ValueError('Expected 30 AI predictions')

    for day, prediction in enumerate(predictions, start=1):
        expected_date = cutoff_date + timedelta(days=day)

        if prediction['date'] != expected_date:
            raise ValueError('AI prediction dates do not match')

    ai_values = [
        prediction['p50']
        for prediction in predictions
    ]

    # Predict each future day using the same last-seven-day
    # average available at the cutoff date.
    baseline_average = (
        sum(history[-BASELINE_DAYS:]) / BASELINE_DAYS
    )

    baseline_values = [
        baseline_average
        for _ in range(TEST_DAYS)
    ]

    ai_mae = calculate_mae(actual, ai_values)
    baseline_mae = calculate_mae(actual, baseline_values)

    return {
        'product_id': product_id,
        'cutoff_date': cutoff_date,
        'test_start': cutoff_date + timedelta(days=1),
        'test_end': end_date,
        'history_days': HISTORY_DAYS,
        'test_days': TEST_DAYS,
        'ai_mae': ai_mae,
        'baseline_mae': baseline_mae,
        'better_model': (
            'chronos' if ai_mae < baseline_mae
            else 'moving_average' if baseline_mae < ai_mae
            else 'tie'
        )
    }
