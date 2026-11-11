
from django import forms
from catalog.models import Product


class SaleForm(forms.Form):
    discount_type = forms.ChoiceField(
        choices=[
            ('none', 'No discount'),
            ('fixed', 'Fixed amount'),
            ('percent', 'Percentage')
        ]
    )

    discount_value = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        initial=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        products = Product.objects.filter(
            is_active=True,
            on_hand__gt=0
        ).order_by('name')

        for number in range(1, 6):
            self.fields[f'product_{number}'] = forms.ModelChoiceField(
                queryset=products,
                required=False,
                label=f'Product {number}'
            )

            self.fields[f'quantity_{number}'] = forms.IntegerField(
                min_value=1,
                required=False,
                label='Quantity'
            )

    def clean(self):
        cleaned_data = super().clean()
        items = []
        selected_products = set()

        for number in range(1, 6):
            product = cleaned_data.get(f'product_{number}')
            quantity = cleaned_data.get(f'quantity_{number}')

            if product is None and quantity is None:
                continue

            if product is None or quantity is None:
                raise forms.ValidationError(
                    'Select both product and quantity for each row.'
                )

            if product.pk in selected_products:
                raise forms.ValidationError(
                    'The same product cannot be selected twice.'
                )

            selected_products.add(product.pk)

            items.append({
                'product_id': product.pk,
                'quantity': quantity
            })

        if not items:
            raise forms.ValidationError(
                'Select at least one product.'
            )

        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')

        if discount_type == 'none' and discount_value != 0:
            raise forms.ValidationError(
                'Discount must be zero when no discount is selected.'
            )

        if (
            discount_type == 'percent'
            and discount_value is not None
            and discount_value > 100
        ):
            raise forms.ValidationError(
                'Percentage discount cannot exceed 100.'
            )

        cleaned_data['items'] = items

        return cleaned_data


class VoidSaleForm(forms.Form):
    reason = forms.CharField(
        label='Reason for voiding',
        widget=forms.Textarea(attrs={'rows': 3}),
        max_length=500
    )

    def clean_reason(self):
        reason = self.cleaned_data['reason'].strip()

        if not reason:
            raise forms.ValidationError('Reason is required')

        return reason