
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO


EXPECTED_COLUMNS = [
    'date',
    'sku',
    'units_sold',
    'gross_revenue'
]


def validate_daily_sales_csv(csv_text):

    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ValueError('CSV file is empty')

    reader = csv.reader(
        StringIO(csv_text.lstrip('\ufeff'))
    )

    header = next(reader, None)

    if header != EXPECTED_COLUMNS:
        raise ValueError(
            'CSV columns must be: '
            'date,sku,units_sold,gross_revenue'
        )

    validated_rows = []
    seen = set()

    for row in reader:
        if not row:
            continue

        line_number = reader.line_num

        if len(row) != 4:
            raise ValueError(
                f'Line {line_number}: Expected four values'
            )

        sale_date, sku, units, revenue = [
            value.strip() for value in row
        ]

        try:
            parsed_date = datetime.strptime(
                sale_date, '%Y-%m-%d'
            ).date()

            if parsed_date.isoformat() != sale_date:
                raise ValueError()

        except ValueError:
            raise ValueError(
                f'Line {line_number}: Invalid date'
            )

        if not sku or len(sku) > 50:
            raise ValueError(
                f'Line {line_number}: Invalid SKU'
            )

        if not units.isascii() or not units.isdigit():
            raise ValueError(
                f'Line {line_number}: Invalid units sold'
            )

        quantity = int(units)

        try:
            amount = Decimal(revenue)
        except (InvalidOperation, ValueError):
            raise ValueError(
                f'Line {line_number}: Invalid revenue'
            )

        if (
            not amount.is_finite()
            or amount < 0
            or amount.as_tuple().exponent < -2
            or (quantity == 0 and amount != 0)
        ):
            raise ValueError(
                f'Line {line_number}: Invalid revenue'
            )

        key = (sku, parsed_date)

        if key in seen:
            raise ValueError(
                f'Line {line_number}: Duplicate product and date'
            )

        seen.add(key)

        validated_rows.append({
            'date': parsed_date,
            'sku': sku,
            'units_sold': quantity,
            'gross_revenue': amount
        })

    if not validated_rows:
        raise ValueError('CSV contains no sales records')

    return validated_rows



def validate_product_skus(validated_rows):

    from catalog.models import Product

    csv_skus = {
        row['sku']
        for row in validated_rows
    }

    existing_skus = set(
        Product.objects.filter(
            sku__in=csv_skus
        ).values_list('sku', flat=True)
    )

    missing_skus = csv_skus - existing_skus

    if missing_skus:
        raise ValueError(
            'Unknown product SKU(s): '
            + ', '.join(sorted(missing_skus))
        )

    return validated_rows
