
from django.test import TestCase
from django.urls import reverse

from .models import CustomUser

from unittest.mock import patch
from smtplib import SMTPException

from django.core import mail
from django.test import override_settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from urllib.parse import urlparse

from .utils import generate_setup_link, send_welcome_email

from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


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



@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class PasswordWorkflowTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='passworduser',
            email='passworduser@example.com',
            password='OldPassword123!',
            role='sales'
        )

    def test_change_password_requires_login(self):
        response = self.client.get(reverse('change_password'))
        self.assertRedirects(
            response,
            reverse('login') + '?next=' + reverse('change_password')
        )

    def test_change_password_page_loads(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('change_password'))
        self.assertEqual(response.status_code, 200)

    def test_valid_password_change_keeps_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('change_password'), {
            'old_password': 'OldPassword123!',
            'new_password1': 'NewPassword456!',
            'new_password2': 'NewPassword456!'
        })

        self.assertRedirects(response, reverse('home'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword456!'))
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.user.pk
        )

    def test_wrong_old_password_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('change_password'), {
            'old_password': 'WrongPassword123!',
            'new_password1': 'NewPassword456!',
            'new_password2': 'NewPassword456!'
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPassword123!'))

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)

    def test_password_reset_sends_email(self):
        response = self.client.post(reverse('password_reset'), {
            'email': self.user.email
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password-reset/confirm/', mail.outbox[0].body)

    def test_unknown_email_sends_nothing(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'unknown@example.com'
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_user_gets_no_reset_email(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(reverse('password_reset'), {
            'email': self.user.email
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_setup_link_contains_valid_token(self):
        response = self.client.get(reverse('login'))
        link = generate_setup_link(response.wsgi_request, self.user)

        path = urlparse(link).path
        parts = path.strip('/').split('/')
        uid = parts[-2]
        token = parts[-1]

        self.assertEqual(
            force_str(urlsafe_base64_decode(uid)),
            str(self.user.pk)
        )
        self.assertTrue(
            default_token_generator.check_token(self.user, token)
        )

    def test_welcome_email_contains_setup_link(self):
        response = self.client.get(reverse('login'))

        send_welcome_email(response.wsgi_request, self.user)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn(self.user.username, mail.outbox[0].body)
        self.assertIn('password-reset/confirm/', mail.outbox[0].body)

    
    def test_password_reset_confirmation_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        reset_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': uid, 'token': token}
        )

        response = self.client.get(reset_url)
        self.assertRedirects(
            response,
            reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': 'set-password'}
            )
        )

        response = self.client.post(
            reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': 'set-password'}
            ),
            {
                'new_password1': 'RecoveredPassword456!',
                'new_password2': 'RecoveredPassword456!'
            }
        )

        self.assertRedirects(
            response,
            reverse('password_reset_complete')
        )

        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password('RecoveredPassword456!')
        )
        self.assertFalse(
            self.user.check_password('OldPassword123!')
        )

    def test_new_employee_can_set_first_password(self):
        employee = CustomUser.objects.create_user(
            username='newsetupuser',
            email='newsetup@example.com',
            role='sales'
        )
        employee.set_unusable_password()
        employee.save()

        response = self.client.get(reverse('login'))
        setup_link = generate_setup_link(
            response.wsgi_request, employee
        )

        path = urlparse(setup_link).path
        response = self.client.get(path)

        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            response.url,
            {
                'new_password1': 'FirstPassword456!',
                'new_password2': 'FirstPassword456!'
            }
        )

        self.assertRedirects(
            response,
            reverse('password_reset_complete')
        )

        employee.refresh_from_db()
        self.assertTrue(employee.has_usable_password())
        self.assertTrue(
            employee.check_password('FirstPassword456!')
        )




