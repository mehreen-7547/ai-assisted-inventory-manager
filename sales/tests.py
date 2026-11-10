
from django.test import TestCase
from django.db import models

from .models import Sale, SaleLine


class SalesModelTests(TestCase):

    def test_sale_fields_exist(self):
        field_names = {
            field.name for field in Sale._meta.fields
        }

        required_fields = {
            'sale_number',
            'status',
            'discount_type',
            'discount_value',
            'subtotal',
            'total',
            'created_by',
            'created_at',
            'voided_by',
            'voided_at',
            'void_reason',
            'submission_key',
        }

        self.assertTrue(required_fields.issubset(field_names))

    def test_sale_line_fields_exist(self):
        field_names = {
            field.name for field in SaleLine._meta.fields
        }

        required_fields = {
            'sale',
            'product',
            'product_name',
            'quantity',
            'unit_price',
            'line_total',
        }

        self.assertTrue(required_fields.issubset(field_names))

    def test_sale_line_relationships_are_protected(self):
        for field_name in ['sale', 'product']:
            field = SaleLine._meta.get_field(field_name)
            self.assertEqual(field.remote_field.on_delete, models.PROTECT)
