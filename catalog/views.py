from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from .models import Supplier

from django.shortcuts import redirect
from .forms import SupplierForm

from django.shortcuts import get_object_or_404



@login_required
@role_required('manager')
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by('name')

    return render(request, 'catalog/supplier_list.html', {
        'suppliers': suppliers,
        'edit_mode': request.GET.get('mode') == 'edit'
    })



@login_required
@role_required('manager')
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('supplier_list')
    else:
        form = SupplierForm()

    return render(request, 'catalog/supplier_form.html', {
        'form': form
    })



@login_required
@role_required('manager')
def supplier_edit(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)

    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)

        if form.is_valid():
            form.save()
            return redirect('supplier_list')
    else:
        form = SupplierForm(instance=supplier)

    return render(request, 'catalog/supplier_form.html', {
        'form': form
    })