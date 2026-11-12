
from django.shortcuts import render

from accounts.decorators import role_required
from .dashboard import get_manager_summary


@role_required('admin', 'manager', 'sales')
def home(request):
    context = {}

    if request.user.role == 'manager':
        context['manager_summary'] = get_manager_summary()

    return render(request, 'core/home.html', context)
