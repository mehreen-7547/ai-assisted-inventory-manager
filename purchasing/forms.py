
from django import forms

from catalog.models import Product, Supplier
from .models import PurchaseOrder


class PurchaseOrderForm(forms.Form):
    MAX_ROWS = 100

    po_number = forms.CharField(
        max_length=20,
        label='Purchase Order Number'
    )

    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.none(),
        empty_label='Select Supplier'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_active=True
        ).order_by('name')

        products = Product.objects.filter(
            is_active=True,
            supplier__is_active=True
        ).order_by('name')

        self.too_many_rows = False

        if self.is_bound:
            row_numbers = set()

            for key in self.data.keys():
                if key.startswith((
                    'product_', 'quantity_', 'unit_cost_'
                )):
                    number = key.rsplit('_', 1)[1]

                    if number.isdigit() and int(number) > 0:
                        row_numbers.add(int(number))

            self.too_many_rows = len(row_numbers) > self.MAX_ROWS
            self.row_numbers = sorted(row_numbers)[:self.MAX_ROWS]
        else:
            self.row_numbers = [1]

        for number in self.row_numbers:
            self.fields[f'product_{number}'] = forms.ModelChoiceField(
                queryset=products,
                required=False,
                label='Product',
                empty_label='Select Product'
            )

            self.fields[f'quantity_{number}'] = forms.IntegerField(
                min_value=1,
                required=False,
                label='Quantity'
            )

            self.fields[f'unit_cost_{number}'] = forms.DecimalField(
                min_value=0,
                max_digits=10,
                decimal_places=2,
                required=False,
                label='Unit Cost'
            )

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_po_number(self):
        po_number = self.cleaned_data['po_number'].strip()

        if PurchaseOrder.objects.filter(
            po_number=po_number
        ).exists():
            raise forms.ValidationError(
                'Purchase order number already exists.'
            )

        return po_number

    def clean(self):
        cleaned_data = super().clean()

        if self.too_many_rows:
            raise forms.ValidationError(
                'Maximum 100 product rows allowed.'
            )

        supplier = cleaned_data.get('supplier')
        items = []
        selected_products = set()

        for number in self.row_numbers:
            product = cleaned_data.get(f'product_{number}')
            quantity = cleaned_data.get(f'quantity_{number}')
            unit_cost = cleaned_data.get(f'unit_cost_{number}')

            if (
                product is None
                and quantity is None
                and unit_cost is None
            ):
                continue

            if (
                product is None
                or quantity is None
                or unit_cost is None
            ):
                raise forms.ValidationError(
                    'Complete product, quantity and unit cost '
                    'for every item.'
                )

            if supplier and product.supplier_id != supplier.pk:
                raise forms.ValidationError(
                    'All products must belong to the selected supplier.'
                )

            if product.pk in selected_products:
                raise forms.ValidationError(
                    'The same product cannot be selected twice.'
                )

            selected_products.add(product.pk)

            items.append({
                'product_id': product.pk,
                'quantity': quantity,
                'unit_cost': unit_cost
            })

        if not items:
            raise forms.ValidationError(
                'Add at least one complete product item.'
            )

        cleaned_data['items'] = items

        return cleaned_data
