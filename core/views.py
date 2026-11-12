
from django.shortcuts import render

from accounts.decorators import role_required
from .dashboard import (
    get_manager_summary,
    get_low_stock_products,
    get_purchase_orders_needing_attention,
    get_recent_stock_movements,
    get_recent_sales,
    get_top_selling_products,
    get_daily_sales_last_seven_days,
    get_sales_staff_summary,
    get_sales_staff_recent_sales,
    get_sales_staff_stock_alerts
)


@role_required('admin', 'manager', 'sales')
def home(request):
    context = {}

    if request.user.role == 'manager':
        context['manager_summary'] = get_manager_summary()

        context['low_stock_products'] = (
            get_low_stock_products()
        )

        context['purchase_orders_attention'] = (
            get_purchase_orders_needing_attention()
        )

        context['recent_stock_movements'] = (
            get_recent_stock_movements()
        )

        context['recent_sales'] = get_recent_sales()

        context['top_selling_products'] = (
            get_top_selling_products()
        )

        context['daily_sales'] = (
            get_daily_sales_last_seven_days()
        )

        context['daily_sales_has_data'] = any(
            item['sales_count'] > 0
            for item in context['daily_sales']
        )

    elif request.user.role == 'sales':
        context['sales_staff_summary'] = (
            get_sales_staff_summary(request.user)
        )

        context['sales_staff_recent_sales'] = (
            get_sales_staff_recent_sales(request.user)
        )

        context['sales_staff_stock_alerts'] = (
            get_sales_staff_stock_alerts()
        )

    return render(request, 'core/home.html', context)
