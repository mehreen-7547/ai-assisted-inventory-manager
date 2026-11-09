
from django.test import TestCase
from django.urls import reverse

from .models import CustomUser

from unittest.mock import patch
from smtplib import SMTPException


class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testemployee',
            email='testemployee@example.com',
            password='TestPassword123!',
            role='sales'
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_valid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testemployee',
            'password': 'TestPassword123!'
        })
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.user.pk
        )

    def test_invalid_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testemployee',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(reverse('login'), {
            'username': 'testemployee',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)

    def test_logout_clears_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)


class EmployeeManagementTests(TestCase):

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='AdminPass123!',
            role='admin'
        )
        self.employee = CustomUser.objects.create_user(
            username='salesuser',
            email='sales@example.com',
            password='SalesPass123!',
            role='sales'
        )
        self.manager = CustomUser.objects.create_user(
            username='manageruser',
            email='manager@example.com',
            password='ManagerPass123!',
            role='manager'
        )
        self.client.force_login(self.admin)

    def test_admin_can_view_employees(self):
        response = self.client.get(reverse('employee_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'salesuser')
        self.assertNotContains(response, 'adminuser')

    def test_non_admin_cannot_access_employee_list(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('employee_list'))
        self.assertRedirects(response, reverse('home'))

    def test_manager_cannot_create_employee(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('create_employee'))
        self.assertRedirects(response, reverse('home'))

    @patch('accounts.views.send_welcome_email')
    def test_admin_can_create_employee(self, mock_email):
        response = self.client.post(reverse('create_employee'), {
            'username': 'newemployee',
            'first_name': 'New',
            'last_name': 'Employee',
            'email': 'new@example.com',
            'role': 'sales'
        })
        self.assertRedirects(response, reverse('employee_list'))
        employee = CustomUser.objects.get(username='newemployee')
        self.assertFalse(employee.has_usable_password())
        mock_email.assert_called_once()

    @patch('accounts.views.send_welcome_email')
    def test_email_failure_keeps_created_employee(self, mock_email):
        mock_email.side_effect = SMTPException('Email failed')
        response = self.client.post(reverse('create_employee'), {
            'username': 'newemployee',
            'first_name': 'New',
            'last_name': 'Employee',
            'email': 'new@example.com',
            'role': 'sales'
        })
        self.assertRedirects(response, reverse('employee_list'))
        self.assertTrue(
            CustomUser.objects.filter(username='newemployee').exists()
        )

    def test_admin_can_edit_employee(self):
        response = self.client.post(
            reverse('edit_employee', args=[self.employee.pk]),
            {
                'first_name': 'Updated',
                'last_name': 'Employee',
                'email': 'sales@example.com',
                'role': 'sales'
            }
        )
        self.assertRedirects(response, reverse('employee_list'))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.first_name, 'Updated')

    def test_admin_can_deactivate_employee(self):
        response = self.client.post(
            reverse('toggle_employee_status', args=[self.employee.pk])
        )
        self.assertRedirects(response, reverse('employee_list'))
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)

    def test_status_change_requires_post(self):
        response = self.client.get(
            reverse('toggle_employee_status', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 405)

    def test_admin_cannot_deactivate_another_admin(self):
        response = self.client.post(
            reverse('toggle_employee_status', args=[self.admin.pk])
        )
        self.assertEqual(response.status_code, 404)

    @patch('accounts.views.send_welcome_email')
    def test_resend_setup_email(self, mock_email):
        self.employee.set_unusable_password()
        self.employee.save()

        response = self.client.post(
            reverse('resend_setup_email', args=[self.employee.pk])
        )
        self.assertRedirects(response, reverse('employee_list'))
        mock_email.assert_called_once()

    @patch('accounts.views.send_welcome_email')
    def test_inactive_employee_gets_no_setup_email(self, mock_email):
        self.employee.is_active = False
        self.employee.set_unusable_password()
        self.employee.save()

        response = self.client.post(
            reverse('resend_setup_email', args=[self.employee.pk])
        )
        self.assertRedirects(response, reverse('employee_list'))
        mock_email.assert_not_called()

    @patch('accounts.views.send_welcome_email')
    def test_resend_email_failure_is_handled(self, mock_email):
        self.employee.set_unusable_password()
        self.employee.save()
        mock_email.side_effect = SMTPException('Email failed')

        response = self.client.post(
            reverse('resend_setup_email', args=[self.employee.pk])
        )
        self.assertRedirects(response, reverse('employee_list'))
        mock_email.assert_called_once()



class EmployeePermissionValidationTests(TestCase):

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admincheck',
            email='admincheck@example.com',
            password='AdminPass123!',
            role='admin'
        )

        self.employee = CustomUser.objects.create_user(
            username='salescheck',
            email='salescheck@example.com',
            password='SalesPass123!',
            role='sales'
        )

        self.manager = CustomUser.objects.create_user(
            username='managercheck',
            email='managercheck@example.com',
            password='ManagerPass123!',
            role='manager'
        )

        self.client.force_login(self.admin)

    def employee_data(self, username='newstaff',
                      email='newstaff@example.com',
                      role='sales'):
        return {
            'username': username,
            'first_name': 'New',
            'last_name': 'Staff',
            'email': email,
            'role': role
        }

    def edit_data(self, email='salescheck@example.com',
                  role='sales'):
        return {
            'first_name': 'Changed',
            'last_name': 'Staff',
            'email': email,
            'role': role
        }

    @patch('accounts.views.send_welcome_email')
    def test_sales_cannot_create_employee(self, mock_email):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse('create_employee'),
            self.employee_data()
        )

        self.assertRedirects(response, reverse('home'))
        self.assertFalse(
            CustomUser.objects.filter(username='newstaff').exists()
        )
        mock_email.assert_not_called()

    def test_manager_cannot_edit_employee(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('edit_employee', args=[self.employee.pk]),
            self.edit_data()
        )

        self.assertRedirects(response, reverse('home'))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.first_name, '')

    def test_sales_cannot_deactivate_employee(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse('toggle_employee_status', args=[self.manager.pk])
        )

        self.assertRedirects(response, reverse('home'))
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)

    @patch('accounts.views.send_welcome_email')
    def test_manager_cannot_resend_setup_email(self, mock_email):
        self.employee.set_unusable_password()
        self.employee.save()
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('resend_setup_email', args=[self.employee.pk])
        )

        self.assertRedirects(response, reverse('home'))
        mock_email.assert_not_called()

    def test_admin_can_reactivate_employee(self):
        self.employee.is_active = False
        self.employee.save()

        response = self.client.post(
            reverse('toggle_employee_status', args=[self.employee.pk])
        )

        self.assertRedirects(response, reverse('employee_list'))
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)

    def test_admin_cannot_edit_admin_using_employee_form(self):
        response = self.client.post(
            reverse('edit_employee', args=[self.admin.pk]),
            self.edit_data()
        )

        self.assertEqual(response.status_code, 404)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, '')

    @patch('accounts.views.send_welcome_email')
    def test_duplicate_email_cannot_create_employee(self, mock_email):
        response = self.client.post(
            reverse('create_employee'),
            self.employee_data(email='salescheck@example.com')
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='newstaff').exists()
        )
        mock_email.assert_not_called()

    @patch('accounts.views.send_welcome_email')
    def test_admin_role_cannot_be_created_from_employee_form(
        self, mock_email
    ):
        response = self.client.post(
            reverse('create_employee'),
            self.employee_data(role='admin')
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(username='newstaff').exists()
        )
        mock_email.assert_not_called()

    @patch('accounts.views.send_welcome_email')
    def test_missing_username_cannot_create_employee(
        self, mock_email
    ):
        response = self.client.post(
            reverse('create_employee'),
            self.employee_data(username='')
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CustomUser.objects.filter(email='newstaff@example.com').exists()
        )
        mock_email.assert_not_called()

    def test_duplicate_email_cannot_update_employee(self):
        response = self.client.post(
            reverse('edit_employee', args=[self.employee.pk]),
            self.edit_data(email='managercheck@example.com')
        )

        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(
            self.employee.email,
            'salescheck@example.com'
        )

    @patch('accounts.views.send_welcome_email')
    def test_existing_password_prevents_setup_email(self, mock_email):
        response = self.client.post(
            reverse('resend_setup_email', args=[self.employee.pk])
        )

        self.assertRedirects(response, reverse('employee_list'))
        mock_email.assert_not_called()

    @patch('accounts.views.send_welcome_email')
    def test_resend_setup_email_requires_post(self, mock_email):
        response = self.client.get(
            reverse('resend_setup_email', args=[self.employee.pk])
        )

        self.assertEqual(response.status_code, 405)
        mock_email.assert_not_called()
