
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate

from sales.models import SaleLine

from django.db import transaction

from catalog.models import Product
from .models import DailySales

from django.utils import timezone
from sales.models import Sale



def get_product_daily_sales(product_id, start_date, end_date):

    if (
        not isinstance(start_date, date)
        or not isinstance(end_date, date)
        or isinstance(start_date, __import__('datetime').datetime)
        or isinstance(end_date, __import__('datetime').datetime)
        or start_date > end_date
    ):
        raise ValueError('Invalid date range')

    sales = (
        SaleLine.objects.filter(
            product_id=product_id,
            sale__status='completed',
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date
        )
        .annotate(
            sale_day=TruncDate('sale__created_at')
        )
        .values('sale_day')
        .annotate(
            total_units=Sum('quantity'),
            total_revenue=Sum('line_total')
        )
    )

    sales_by_date = {
        item['sale_day']: item
        for item in sales
    }

    daily_data = []
    current_date = start_date

    while current_date <= end_date:
        record = sales_by_date.get(current_date)

        daily_data.append({
            'date': current_date,
            'units_sold': (
                record['total_units'] if record else 0
            ),
            'gross_revenue': (
                record['total_revenue']
                if record else Decimal('0.00')
            )
        })

        current_date += timedelta(days=1)

    return daily_data




def save_product_daily_sales(product_id, start_date, end_date):

    daily_data = get_product_daily_sales(
        product_id,
        start_date,
        end_date
    )

    product = Product.objects.get(pk=product_id)

    with transaction.atomic():

        for row in daily_data:
            DailySales.objects.update_or_create(
                product=product,
                date=row['date'],
                defaults={
                    'units_sold': row['units_sold'],
                    'gross_revenue': row['gross_revenue']
                }
            )

    return len(daily_data)




def save_all_product_daily_sales():

    first_sale = (
        Sale.objects.filter(
            status='completed'
        ).order_by('created_at').first()
    )

    if first_sale is None:
        raise ValueError('No completed sales available')

    start_date = timezone.localtime(
        first_sale.created_at
    ).date()

    end_date = timezone.localdate()

    product_count = 0
    total_records = 0

    products = Product.objects.all().order_by('pk')

    for product in products:
        saved = save_product_daily_sales(
            product.pk,
            start_date,
            end_date
        )

        product_count += 1
        total_records += saved

    return {
        'products': product_count,
        'start_date': start_date,
        'end_date': end_date,
        'records': total_records
    }
