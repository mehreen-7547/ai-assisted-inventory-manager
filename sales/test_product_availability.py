
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from inventory.services import change_stock

from .forms import SaleForm
from .models import Sale


class SaleProductAvailabilityTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username='availability_sales_user',
            email='availability@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.supplier = Supplier.objects.create(
            name='Availability Test Supplier'
        )

        self.notebook = Product.objects.create(
            sku='AVAIL-NOTE-001',
            name='Availability Notebook',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('50.00')
        )

        self.pen = Product.objects.create(
            sku='AVAIL-PEN-001',
            name='Availability Pen',
            category='Stationery',
            supplier=self.supplier,
            unit_price=Decimal('10.00')
        )

        change_stock(
            product_id=self.notebook.pk,
            delta=10,
            movement_type='opening',
            reason='Opening stock for availability tests',
            user=self.user
        )

    def sale_data(self, **kwargs):
        data = {
            'discount_type': 'none',
            'discount_value': '0',
            'product_1': self.notebook.pk,
            'quantity_1': 1
        }
        data.update(kwargs)
        return data

    def test_active_product_with_stock_is_available(self):
        form = SaleForm()

        products = form.fields['product_1'].queryset

        self.assertIn(self.notebook, products)

    def test_active_product_without_stock_is_excluded(self):
        form = SaleForm()

        products = form.fields['product_1'].queryset

        self.assertNotIn(self.pen, products)

    def test_inactive_product_with_stock_is_excluded(self):
        self.notebook.is_active = False
        self.notebook.save(update_fields=['is_active'])

        form = SaleForm()

        products = form.fields['product_1'].queryset

        self.assertNotIn(self.notebook, products)

    def test_restocked_product_becomes_available(self):
        change_stock(
            product_id=self.pen.pk,
            delta=5,
            movement_type='adjustment',
            reason='Restock pen for sale',
            user=self.user
        )

        form = SaleForm()

        products = form.fields['product_1'].queryset

        self.assertIn(self.pen, products)

    def test_zero_stock_product_cannot_be_submitted(self):
        form = SaleForm(data=self.sale_data(
            product_1=self.pen.pk
        ))

        self.assertFalse(form.is_valid())
        self.assertIn('product_1', form.errors)

    def test_inactive_product_cannot_be_submitted(self):
        self.notebook.is_active = False
        self.notebook.save(update_fields=['is_active'])

        form = SaleForm(data=self.sale_data())

        self.assertFalse(form.is_valid())
        self.assertIn('product_1', form.errors)

    def test_sale_form_starts_with_one_product_row(self):
        form = SaleForm()

        self.assertEqual(form.row_numbers, [1])
        self.assertIn('product_1', form.fields)
        self.assertIn('quantity_1', form.fields)
        self.assertNotIn('product_2', form.fields)

    def test_dynamic_product_rows_are_recognized(self):
        form = SaleForm(data=self.sale_data(
            product_3=self.notebook.pk,
            quantity_3=2,
            product_1='',
            quantity_1=''
        ))

        self.assertEqual(form.row_numbers, [1, 3])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data['items'],
            [{
                'product_id': self.notebook.pk,
                'quantity': 2
            }]
        )

    def test_duplicate_dynamic_products_are_rejected(self):
        form = SaleForm(data=self.sale_data(
            product_3=self.notebook.pk,
            quantity_3=2
        ))

        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_more_than_100_rows_are_rejected(self):
        data = self.sale_data()

        for number in range(2, 102):
            data[f'product_{number}'] = ''
            data[f'quantity_{number}'] = ''

        form = SaleForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_sale_page_shows_only_in_stock_products(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.notebook.name)
        self.assertNotContains(response, self.pen.name)

    def test_sale_page_explains_product_availability(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Only active products with available stock are shown.'
        )

    def test_restocked_pen_appears_on_sale_page(self):
        change_stock(
            product_id=self.pen.pk,
            delta=5,
            movement_type='adjustment',
            reason='Restock pen',
            user=self.user
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse('sale_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pen.name)

    def test_multiple_products_can_be_sold(self):
        change_stock(
            product_id=self.pen.pk,
            delta=5,
            movement_type='adjustment',
            reason='Restock pen',
            user=self.user
        )

        self.client.force_login(self.user)

        response = self.client.post(
            reverse('sale_create'),
            {
                'submission_key': str(uuid4()),
                'discount_type': 'none',
                'discount_value': '0',
                'product_1': self.notebook.pk,
                'quantity_1': 2,
                'product_3': self.pen.pk,
                'quantity_3': 3
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)

        self.notebook.refresh_from_db()
        self.pen.refresh_from_db()

        self.assertEqual(self.notebook.on_hand, 8)
        self.assertEqual(self.pen.on_hand, 2)

        sale = Sale.objects.get()

        self.assertEqual(sale.lines.count(), 2)
        self.assertEqual(sale.total, Decimal('130.00'))
