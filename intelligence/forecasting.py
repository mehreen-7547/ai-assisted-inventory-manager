from datetime import timedelta
from functools import lru_cache
from math import isfinite

from .forecasting_data import get_forecasting_data


MODEL_NAME = 'amazon/chronos-bolt-tiny'
FORECAST_DAYS = 30


@lru_cache(maxsize=1)
def load_forecasting_model():
    from chronos import BaseChronosPipeline

    return BaseChronosPipeline.from_pretrained(
        MODEL_NAME,
        device_map='cpu'
    )


def forecast_product_demand(product_id, end_date):
    import torch

    history = get_forecasting_data(
        product_id,
        end_date
    )

    context = torch.tensor(
        history,
        dtype=torch.float32
    ).unsqueeze(0)

    model = load_forecasting_model()

    with torch.inference_mode():
        quantiles, _ = model.predict_quantiles(
            context,
            prediction_length=FORECAST_DAYS,
            quantile_levels=[0.1, 0.5, 0.9]
        )

    result = quantiles[0]

    if result.ndim == 3:
        result = result[0]

    if tuple(result.shape) != (FORECAST_DAYS, 3):
        raise ValueError('Unexpected AI forecast shape')

    if not torch.isfinite(result).all().item():
        raise ValueError('AI forecast contains invalid numbers')

    predictions = []

    for day, values in enumerate(result.tolist(), start=1):
        lower, middle, upper = values

        if not all(isfinite(v) for v in values):
            raise ValueError('AI forecast contains invalid numbers')

        lower = max(0.0, float(lower))
        middle = max(0.0, float(middle))
        upper = max(0.0, float(upper))

        # Keep displayed quantiles in increasing order.
        lower, middle, upper = sorted(
            [lower, middle, upper]
        )

        predictions.append({
            'date': end_date + timedelta(days=day),
            'p10': round(lower, 2),
            'p50': round(middle, 2),
            'p90': round(upper, 2)
        })

    return {
        'product_id': product_id,
        'model': MODEL_NAME,
        'history_days': len(history),
        'forecast_days': FORECAST_DAYS,
        'predictions': predictions
    }
