from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from .models import Supplier, Product

from django.shortcuts import redirect
from .forms import SupplierForm, ProductForm

from django.shortcuts import get_object_or_404

from django.views.decorators.http import require_POST





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



@login_required
@role_required('manager')
@require_POST
def toggle_supplier_status(request, supplier_id):

    supplier = get_object_or_404(Supplier, id=supplier_id)

    supplier.is_active = not supplier.is_active
    supplier.save(update_fields=['is_active'])

    return redirect('supplier_list')




@login_required
@role_required('manager', 'sales')
def product_list(request):
    products = Product.objects.select_related(
        'supplier'
    ).all().order_by('name')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'edit_mode': (
            request.user.role == 'manager'
            and request.GET.get('mode') == 'edit'
        )
    })




@login_required
@role_required('manager')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()

    return render(request, 'catalog/product_form.html', {
        'form': form
    })



@login_required
@role_required('manager')
def product_edit(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id
    )

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            instance=product
        )

        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'catalog/product_form.html', {
        'form': form
    })
