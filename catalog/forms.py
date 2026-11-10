from django import forms
from .models import Supplier, Product


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone', 'email', 'address']


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        fields = [
            'sku',
            'name',
            'category',
            'supplier',
            'unit_price',
            'lead_time_days',
            'safety_stock'
        ]

    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        suppliers = Supplier.objects.filter(
            is_active=True
        )

        if self.instance.pk:
            suppliers = (
                Supplier.objects.filter(is_active=True)
                | Supplier.objects.filter(
                    pk=self.instance.supplier_id
                )
            )

        self.fields['supplier'].queryset = (
            suppliers.distinct().order_by('name')
        )

