
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product, Supplier
from purchasing.models import PurchaseOrder, PurchaseOrderLine
from sales.models import Sale


class ModuleSixAuthorizationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.admin = User.objects.create_user(
            username='final_admin',
            email='final_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        cls.manager = User.objects.create_user(
            username='final_manager',
            email='final_manager@example.com',
            password='TestPassword123!',
            role='manager'
        )

        cls.sales = User.objects.create_user(
            username='final_sales',
            email='final_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        cls.other_sales = User.objects.create_user(
            username='final_other_sales',
            email='final_other_sales@example.com',
            password='TestPassword123!',
            role='sales'
        )

        cls.pending = User.objects.create_user(
            username='final_pending',
            email='final_pending@example.com',
            password='TestPassword123!',
            role='sales'
        )

        cls.pending.set_unusable_password()
        cls.pending.save(update_fields=['password'])

        cls.supplier = Supplier.objects.create(
            name='Final Authorization Supplier'
        )

        cls.product = Product.objects.create(
            sku='FINAL-AUTH-001',
            name='Final Authorization Product',
            category='Testing',
            supplier=cls.supplier,
            unit_price=Decimal('100.00'),
            on_hand=20,
            safety_stock=5
        )

        cls.order = PurchaseOrder.objects.create(
            po_number='FINAL-PO-001',
            supplier=cls.supplier,
            created_by=cls.manager,
            status='ordered'
        )

        PurchaseOrderLine.objects.create(
            purchase_order=cls.order,
            product=cls.product,
            quantity_ordered=10,
            unit_cost=Decimal('75.00')
        )

        cls.own_sale = Sale.objects.create(
            sale_number='FINAL-OWN',
            submission_key='final-own',
            created_by=cls.sales,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00')
        )

        cls.other_sale = Sale.objects.create(
            sale_number='FINAL-OTHER',
            submission_key='final-other',
            created_by=cls.other_sales,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00')
        )

    def assert_home_redirect(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('home')
        )

    def test_anonymous_users_redirect_to_login(self):
        urls = [
            reverse('home'),
            reverse('employee_list'),
            reverse('supplier_list'),
            reverse('product_list'),
            reverse(
                'stock_adjustment',
                args=[self.product.pk]
            ),
            reverse('sale_list'),
            reverse(
                'sale_detail',
                args=[self.own_sale.pk]
            ),
            reverse('purchase_order_list'),
            reverse(
                'goods_receipt_create',
                args=[self.order.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    302
                )

                self.assertTrue(
                    response.url.startswith(
                        reverse('login') + '?next='
                    )
                )

    def test_dashboard_context_is_separated_by_role(self):
        cases = [
            (
                self.admin,
                'admin_summary'
            ),
            (
                self.manager,
                'manager_summary'
            ),
            (
                self.sales,
                'sales_staff_summary'
            )
        ]

        keys = [
            'admin_summary',
            'manager_summary',
            'sales_staff_summary'
        ]

        for user, expected_key in cases:
            with self.subTest(role=user.role):
                self.client.force_login(user)

                response = self.client.get(
                    reverse('home')
                )

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertIn(
                    expected_key,
                    response.context
                )

                for key in keys:
                    if key != expected_key:
                        self.assertNotIn(
                            key,
                            response.context
                        )

    def test_admin_can_access_employee_pages(self):
        self.client.force_login(self.admin)

        urls = [
            reverse('employee_list'),
            reverse('create_employee'),
            reverse(
                'edit_employee',
                args=[self.pending.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200
                )

    def test_other_roles_cannot_manage_employees(self):
        urls = [
            reverse('employee_list'),
            reverse('create_employee'),
            reverse(
                'edit_employee',
                args=[self.pending.pk]
            )
        ]

        actions = [
            reverse(
                'toggle_employee_status',
                args=[self.pending.pk]
            ),
            reverse(
                'resend_setup_email',
                args=[self.pending.pk]
            )
        ]

        for user in [self.manager, self.sales]:
            self.client.force_login(user)

            for url in urls:
                with self.subTest(
                    role=user.role, url=url
                ):
                    self.assert_home_redirect(
                        self.client.get(url)
                    )

            for url in actions:
                with self.subTest(
                    role=user.role, action=url
                ):
                    self.assert_home_redirect(
                        self.client.post(url)
                    )

        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)
        self.assertFalse(
            self.pending.has_usable_password()
        )

    def test_employee_actions_reject_get(self):
        self.client.force_login(self.admin)

        urls = [
            reverse(
                'toggle_employee_status',
                args=[self.pending.pk]
            ),
            reverse(
                'resend_setup_email',
                args=[self.pending.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    405
                )

        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)

    def test_manager_can_access_inventory_pages(self):
        self.client.force_login(self.manager)

        urls = [
            reverse('supplier_list'),
            reverse('supplier_create'),
            reverse(
                'supplier_edit',
                args=[self.supplier.pk]
            ),
            reverse('product_list'),
            reverse('product_create'),
            reverse(
                'product_edit',
                args=[self.product.pk]
            ),
            reverse(
                'product_stock_history',
                args=[self.product.pk]
            ),
            reverse(
                'stock_adjustment',
                args=[self.product.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200
                )

    def test_non_managers_cannot_change_inventory(self):
        restricted_urls = [
            reverse('supplier_list'),
            reverse('supplier_create'),
            reverse(
                'supplier_edit',
                args=[self.supplier.pk]
            ),
            reverse('product_create'),
            reverse(
                'product_edit',
                args=[self.product.pk]
            ),
            reverse(
                'product_stock_history',
                args=[self.product.pk]
            ),
            reverse(
                'stock_adjustment',
                args=[self.product.pk]
            )
        ]

        status_urls = [
            reverse(
                'toggle_supplier_status',
                args=[self.supplier.pk]
            ),
            reverse(
                'toggle_product_status',
                args=[self.product.pk]
            )
        ]

        for user in [self.admin, self.sales]:
            self.client.force_login(user)

            for url in restricted_urls:
                with self.subTest(
                    role=user.role, url=url
                ):
                    self.assert_home_redirect(
                        self.client.get(url)
                    )

            for url in status_urls:
                with self.subTest(
                    role=user.role, action=url
                ):
                    self.assert_home_redirect(
                        self.client.post(url)
                    )

        self.supplier.refresh_from_db()
        self.product.refresh_from_db()

        self.assertTrue(self.supplier.is_active)
        self.assertTrue(self.product.is_active)

    def test_catalog_status_actions_reject_get(self):
        self.client.force_login(self.manager)

        urls = [
            reverse(
                'toggle_supplier_status',
                args=[self.supplier.pk]
            ),
            reverse(
                'toggle_product_status',
                args=[self.product.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    405
                )

        self.supplier.refresh_from_db()
        self.product.refresh_from_db()

        self.assertTrue(self.supplier.is_active)
        self.assertTrue(self.product.is_active)

    def test_sales_can_view_products_but_admin_cannot(self):
        self.client.force_login(self.sales)

        response = self.client.get(
            reverse('product_list')
        )

        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.admin)

        self.assert_home_redirect(
            self.client.get(
                reverse('product_list')
            )
        )

    def test_manager_can_access_purchasing_pages(self):
        self.client.force_login(self.manager)

        urls = [
            reverse('purchase_order_create'),
            reverse('purchase_order_list'),
            reverse(
                'purchase_order_detail',
                args=[self.order.pk]
            ),
            reverse(
                'goods_receipt_create',
                args=[self.order.pk]
            )
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    200
                )

    def test_other_roles_cannot_access_purchasing(self):
        urls = [
            reverse('purchase_order_create'),
            reverse('purchase_order_list'),
            reverse(
                'purchase_order_detail',
                args=[self.order.pk]
            ),
            reverse(
                'goods_receipt_create',
                args=[self.order.pk]
            )
        ]

        status_url = reverse(
            'purchase_order_status',
            args=[self.order.pk]
        )

        for user in [self.admin, self.sales]:
            self.client.force_login(user)

            for url in urls:
                with self.subTest(
                    role=user.role, url=url
                ):
                    self.assert_home_redirect(
                        self.client.get(url)
                    )

            self.assert_home_redirect(
                self.client.post(
                    status_url,
                    {'status': 'cancelled'}
                )
            )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            'ordered'
        )

    def test_purchase_order_status_rejects_get(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                'purchase_order_status',
                args=[self.order.pk]
            )
        )

        self.assertEqual(response.status_code, 405)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            'ordered'
        )

    def test_sales_pages_allow_sales_and_manager(self):
        urls = [
            reverse('sale_list'),
            reverse('sale_create'),
            reverse(
                'sale_detail',
                args=[self.own_sale.pk]
            )
        ]

        for user in [self.sales, self.manager]:
            self.client.force_login(user)

            for url in urls:
                with self.subTest(
                    role=user.role, url=url
                ):
                    response = self.client.get(url)

                    self.assertEqual(
                        response.status_code,
                        200
                    )

        self.client.force_login(self.admin)

        for url in urls:
            with self.subTest(url=url):
                self.assert_home_redirect(
                    self.client.get(url)
                )

    def test_sales_staff_cannot_view_coworker_sale(self):
        self.client.force_login(self.sales)

        own_response = self.client.get(
            reverse(
                'sale_detail',
                args=[self.own_sale.pk]
            )
        )

        self.assertEqual(
            own_response.status_code,
            200
        )

        other_response = self.client.get(
            reverse(
                'sale_detail',
                args=[self.other_sale.pk]
            )
        )

        self.assert_home_redirect(other_response)

        self.client.force_login(self.manager)

        manager_response = self.client.get(
            reverse(
                'sale_detail',
                args=[self.other_sale.pk]
            )
        )

        self.assertEqual(
            manager_response.status_code,
            200
        )

    def test_only_manager_can_open_sale_void_page(self):
        url = reverse(
            'sale_void',
            args=[self.own_sale.pk]
        )

        self.client.force_login(self.manager)

        self.assertEqual(
            self.client.get(url).status_code,
            200
        )

        for user in [self.admin, self.sales]:
            self.client.force_login(user)

            self.assert_home_redirect(
                self.client.get(url)
            )

            self.assert_home_redirect(
                self.client.post(
                    url,
                    {'reason': 'Unauthorized attempt'}
                )
            )

        self.own_sale.refresh_from_db()

        self.assertEqual(
            self.own_sale.status,
            'completed'
        )

    def test_logout_requires_post(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('logout')
        )

        self.assertEqual(response.status_code, 405)

        self.assertIn(
            '_auth_user_id',
            self.client.session
        )
