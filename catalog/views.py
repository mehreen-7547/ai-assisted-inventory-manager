from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from .models import Supplier


@login_required
@role_required('manager')
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by('name')

    return render(request, 'catalog/supplier_list.html', {
        'suppliers': suppliers
    })