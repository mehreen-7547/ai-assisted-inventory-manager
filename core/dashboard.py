from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from catalog.models import Product
from purchasing.models import PurchaseOrder

from inventory.models import StockMovement

from django.db.models.functions import TruncDate
from sales.models import Sale, SaleLine



def get_manager_summary():
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)

    active_products = Product.objects.filter(
        is_active=True,
        supplier__is_active=True
    )

    low_stock = active_products.filter(
        on_hand__gt=0,
        on_hand__lte=F('safety_stock')
    ).count()

    out_of_stock = active_products.filter(
        on_hand=0
    ).count()

    completed_sales = Sale.objects.filter(
        status='completed'
    )

    sales_today = completed_sales.filter(
        created_at__date=today
    ).aggregate(
        count=Count('id'),
        total=Sum('total')
    )

    sales_week = completed_sales.filter(
        created_at__date__gte=seven_days_ago,
        created_at__date__lte=today
    ).aggregate(
        count=Count('id'),
        total=Sum('total')
    )

    open_orders = PurchaseOrder.objects.filter(
        supplier__is_active=True,
        status__in=['ordered', 'partially_received']
    )

    overdue_orders = open_orders.filter(
        expected_delivery_date__lt=today
    )

    return {
        'low_stock_count': low_stock,
        'out_of_stock_count': out_of_stock,
        'sales_today_count': sales_today['count'],
        'sales_today_total': (
            sales_today['total'] or Decimal('0.00')
        ),
        'sales_week_count': sales_week['count'],
        'sales_week_total': (
            sales_week['total'] or Decimal('0.00')
        ),
        'open_orders_count': open_orders.count(),
        'overdue_orders_count': overdue_orders.count()
    }




def get_low_stock_products():
    return list(
        Product.objects.filter(
            is_active=True,
            supplier__is_active=True
        ).filter(
            Q(on_hand=0)
            | Q(
                on_hand__gt=0,
                on_hand__lte=F('safety_stock')
            )
        ).select_related('supplier').order_by(
            'on_hand', 'name', 'pk'
        )[:10]
    )



def get_purchase_orders_needing_attention():
    today = timezone.localdate()

    orders = PurchaseOrder.objects.filter(
        supplier__is_active=True,
        status__in=['ordered', 'partially_received']
    ).select_related('supplier').order_by(
        F('expected_delivery_date').asc(nulls_last=True),
        'created_at',
        'pk'
    )[:5]

    results = []

    for order in orders:
        days_overdue = 0

        if (
            order.expected_delivery_date
            and order.expected_delivery_date < today
        ):
            days_overdue = (
                today - order.expected_delivery_date
            ).days

        results.append({
            'order': order,
            'days_overdue': days_overdue
        })

    return results



def get_recent_stock_movements():
    return list(
        StockMovement.objects.filter(
            product__is_active=True,
            product__supplier__is_active=True
        ).select_related(
            'product',
            'created_by'
        ).order_by(
            '-created_at',
            '-pk'
        )[:8]
    )


def get_recent_sales():
    return list(
        Sale.objects.select_related(
            'created_by'
        ).order_by(
            '-created_at',
            '-pk'
        )[:5]
    )



def get_top_selling_products():
    today = timezone.localdate()
    start_date = today - timedelta(days=29)

    return list(
        SaleLine.objects.filter(
            sale__status='completed',
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=today,
            product__is_active=True,
            product__supplier__is_active=True
        ).values(
            'product_id',
            product_label=F('product__name')
        ).annotate(
            units_sold=Sum('quantity'),
            gross_revenue=Sum('line_total')
        ).order_by(
            '-units_sold',
            'product_label',
            'product_id'
        )[:5]
    )


def get_daily_sales_last_seven_days():
    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    sales_by_day = (
        Sale.objects.filter(
            status='completed',
            created_at__date__gte=start_date,
            created_at__date__lte=today
        ).annotate(
            sale_date=TruncDate('created_at')
        ).values(
            'sale_date'
        ).annotate(
            sales_count=Count('id'),
            total=Sum('total')
        ).order_by('sale_date')
    )

    totals = {
        item['sale_date']: item
        for item in sales_by_day
    }

    days = []

    for number in range(7):
        day = start_date + timedelta(days=number)
        item = totals.get(day)

        days.append({
            'date': day,
            'sales_count': (
                item['sales_count'] if item else 0
            ),
            'total': (
                item['total'] if item
                else Decimal('0.00')
            )
        })

    highest_total = max(
        item['total'] for item in days
    )

    for item in days:
        if highest_total > 0:
            item['bar_percent'] = int(
                item['total'] * 100 / highest_total
            )
        else:
            item['bar_percent'] = 0

    return days
