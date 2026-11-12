
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.dashboard import (
    get_admin_summary,
    get_pending_password_setup,
    get_recent_users
)


class AdminDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.admin = User.objects.create_user(
            username='dashboard_admin',
            email='dashboard_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        self.manager = User.objects.create_user(
            username='dashboard_manager_admin_test',
            email='dashboard_manager_admin@example.com',
            password='TestPassword123!',
            role='manager'
        )

        self.sales_user = User.objects.create_user(
            username='dashboard_sales_admin_test',
            email='dashboard_sales_admin@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.pending = User.objects.create_user(
            username='pending_employee',
            email='pending_employee@example.com',
            password='TestPassword123!',
            role='sales'
        )

        self.pending.set_unusable_password()
        self.pending.save(update_fields=['password'])

        self.inactive = User.objects.create_user(
            username='inactive_employee',
            email='inactive_employee@example.com',
            password='TestPassword123!',
            role='sales',
            is_active=False
        )

        self.inactive_pending = User.objects.create_user(
            username='inactive_pending',
            email='inactive_pending@example.com',
            password='TestPassword123!',
            role='manager',
            is_active=False
        )

        self.inactive_pending.set_unusable_password()
        self.inactive_pending.save(update_fields=['password'])

    def test_summary_counts_active_and_deactivated(self):
        summary = get_admin_summary()

        self.assertEqual(summary['active_count'], 4)
        self.assertEqual(summary['inactive_count'], 2)

    def test_active_role_counts(self):
        summary = get_admin_summary()

        self.assertEqual(summary['active_admin_count'], 1)
        self.assertEqual(summary['active_manager_count'], 1)
        self.assertEqual(summary['active_sales_count'], 2)

    def test_pending_only_active_employees(self):
        summary = get_admin_summary()
        pending = get_pending_password_setup()

        self.assertEqual(
            summary['pending_setup_count'],
            1
        )

        self.assertEqual(
            [employee.username for employee in pending],
            ['pending_employee']
        )

        self.assertFalse(
            pending[0].has_usable_password()
        )

    def test_pending_excludes_admin_accounts(self):
        User = get_user_model()

        another_admin = User.objects.create_user(
            username='unusable_admin',
            email='unusable_admin@example.com',
            password='TestPassword123!',
            role='admin'
        )

        another_admin.set_unusable_password()
        another_admin.save(update_fields=['password'])

        pending = get_pending_password_setup()
        summary = get_admin_summary()

        self.assertEqual(len(pending), 1)
        self.assertEqual(
            summary['pending_setup_count'],
            1
        )

        self.assertNotIn(
            another_admin,
            pending
        )

    def test_password_setup_removes_pending_employee(self):
        self.pending.set_password('NewPassword123!')
        self.pending.save(update_fields=['password'])

        summary = get_admin_summary()
        pending = get_pending_password_setup()

        self.assertEqual(
            summary['pending_setup_count'],
            0
        )

        self.assertEqual(pending, [])

    def test_recent_users_limited_to_five(self):
        recent = get_recent_users()

        self.assertEqual(len(recent), 5)

        self.assertEqual(
            recent[0].username,
            'inactive_pending'
        )

        self.assertNotIn(self.admin, recent)

    def test_admin_dashboard_displays_account_information(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Active Accounts'
        )

        self.assertContains(
            response,
            'Active Accounts by Role'
        )

        self.assertContains(
            response,
            'Deactivated Accounts'
        )

        self.assertContains(
            response,
            'Pending Password Setup'
        )

        self.assertContains(
            response,
            'Employees Awaiting Password Setup'
        )

        self.assertContains(
            response,
            'Recently Added Accounts'
        )

        self.assertContains(
            response,
            'pending_employee'
        )

        self.assertContains(
            response,
            'Resend Setup Email'
        )

        self.assertNotContains(
            response,
            'Top-selling Products'
        )

        self.assertNotContains(
            response,
            'My Sales Today'
        )

        self.assertNotContains(
            response,
            'Purchase Orders Needing Attention'
        )

        self.assertNotIn(
            'manager_summary',
            response.context
        )

        self.assertNotIn(
            'sales_staff_summary',
            response.context
        )

    @patch('accounts.views.send_welcome_email')
    def test_pending_resend_action_uses_existing_route(
        self, mock_email
    ):
        self.client.force_login(self.admin)

        url = reverse(
            'resend_setup_email',
            args=[self.pending.pk]
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, url)

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('employee_list')
        )

        mock_email.assert_called_once()

        self.assertEqual(
            mock_email.call_args.args[1].pk,
            self.pending.pk
        )

    def test_resend_email_requires_post(self):
        self.client.force_login(self.admin)

        url = reverse(
            'resend_setup_email',
            args=[self.pending.pk]
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

    def test_manager_cannot_see_admin_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            'Employees Awaiting Password Setup'
        )

        self.assertNotContains(
            response,
            'Recently Added Accounts'
        )

        self.assertNotIn(
            'admin_summary',
            response.context
        )

        self.assertNotIn(
            'pending_password_setup',
            response.context
        )

    def test_sales_cannot_see_admin_dashboard(self):
        self.client.force_login(self.sales_user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            'Employees Awaiting Password Setup'
        )

        self.assertNotContains(
            response,
            'Recently Added Accounts'
        )

        self.assertNotContains(
            response,
            'pending_employee'
        )

        self.assertNotIn(
            'admin_summary',
            response.context
        )

        self.assertNotIn(
            'recent_users',
            response.context
        )

    def test_empty_pending_setup_message(self):
        self.pending.set_password('NewPassword123!')
        self.pending.save(update_fields=['password'])

        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        self.assertContains(
            response,
            'No active employees are awaiting password setup.'
        )

        self.assertNotContains(
            response,
            'Resend Setup Email'
        )

    def test_inactive_employee_has_no_resend_action(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        inactive_url = reverse(
            'resend_setup_email',
            args=[self.inactive_pending.pk]
        )

        active_url = reverse(
            'resend_setup_email',
            args=[self.pending.pk]
        )

        self.assertContains(response, active_url)
        self.assertNotContains(response, inactive_url)
