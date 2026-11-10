
from django import forms


class StockAdjustmentForm(forms.Form):
    expected_balance = forms.IntegerField(
        min_value=0,
        widget=forms.HiddenInput
    )

    counted_quantity = forms.IntegerField(
        min_value=0,
        label='Physically Counted Quantity'
    )

    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Reason for Adjustment'
    )
