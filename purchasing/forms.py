
from django import forms

from catalog.models import Product, Supplier
from .models import PurchaseOrder

from .models import PurchaseOrderLine


class PurchaseOrderForm(forms.Form):
    MAX_ROWS = 100

    # Optional hidden field for compatibility with existing tests.
    # The browser does not ask the Manager to enter this number.
    po_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.HiddenInput()
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
                empty_label='Select Product'
            )

            self.fields[f'quantity_{number}'] = forms.IntegerField(
                min_value=1,
                required=False
            )

            self.fields[f'unit_cost_{number}'] = forms.DecimalField(
                min_value=0,
                max_digits=10,
                decimal_places=2,
                required=False
            )

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_po_number(self):
        po_number = self.cleaned_data.get('po_number', '').strip()

        if po_number and PurchaseOrder.objects.filter(
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


class GoodsReceiptForm(forms.Form):

    def __init__(self, *args, purchase_order=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.purchase_order = purchase_order
        self.order_lines = []

        if purchase_order is None:
            return

        lines = PurchaseOrderLine.objects.filter(
            purchase_order=purchase_order
        ).select_related('product').order_by('pk')

        for line in lines:
            remaining = (
                line.quantity_ordered - line.quantity_received
            )

            if remaining <= 0:
                continue

            self.order_lines.append(line)

            self.fields[f'received_{line.pk}'] = (
                forms.IntegerField(
                    label='Usable Quantity',
                    min_value=0,
                    max_value=remaining,
                    initial=0,
                    required=True
                )
            )

            self.fields[f'damaged_{line.pk}'] = (
                forms.IntegerField(
                    label='Damaged Quantity',
                    min_value=0,
                    max_value=remaining,
                    initial=0,
                    required=True
                )
            )

    def clean(self):
        cleaned_data = super().clean()

        if not self.order_lines:
            raise forms.ValidationError(
                'No products are awaiting delivery.'
            )

        items = []

        for line in self.order_lines:
            received = cleaned_data.get(f'received_{line.pk}')
            damaged = cleaned_data.get(f'damaged_{line.pk}')

            if received is None or damaged is None:
                continue

            remaining = (
                line.quantity_ordered - line.quantity_received
            )

            if received + damaged > remaining:
                raise forms.ValidationError(
                    f'{line.product.name}: '
                    'Quantity exceeds the remaining order.'
                )

            if received + damaged > 0:
                items.append({
                    'product_id': line.product_id,
                    'quantity_received': received,
                    'quantity_damaged': damaged
                })

        if not items and not self.errors:
            raise forms.ValidationError(
                'Enter a received or damaged quantity '
                'for at least one product.'
            )

        cleaned_data['items'] = items

        return cleaned_data
