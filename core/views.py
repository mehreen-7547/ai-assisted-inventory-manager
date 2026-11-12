
from django.shortcuts import render

from accounts.decorators import role_required
from .dashboard import get_manager_summary, get_low_stock_products


@role_required('admin', 'manager', 'sales')
def home(request):
    context = {}

    if request.user.role == 'manager':
        context['manager_summary'] = get_manager_summary()
        context['low_stock_products'] = get_low_stock_products()

    return render(request, 'core/home.html', context)
