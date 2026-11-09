
from django.test import TestCase
from django.urls import reverse

from .models import CustomUser


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
