
from django.shortcuts import render

from accounts.decorators import role_required
from .dashboard import (
    get_manager_summary,
    get_low_stock_products,
    get_purchase_orders_needing_attention,
    get_recent_stock_movements,
    get_recent_sales
)


@role_required('admin', 'manager', 'sales')
def home(request):
    context = {}

    if request.user.role == 'manager':
        context['manager_summary'] = get_manager_summary()
        context['low_stock_products'] = get_low_stock_products()
        context['purchase_orders_attention'] = (
            get_purchase_orders_needing_attention()
        )
        context['recent_stock_movements'] = (
            get_recent_stock_movements()
        )
        context['recent_sales'] = get_recent_sales()

    return render(request, 'core/home.html', context)
