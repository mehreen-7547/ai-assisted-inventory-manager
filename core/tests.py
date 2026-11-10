
"""Module 0 foundation checks."""

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.urls import reverse


class ModuleZeroTests(TestCase):
    def test_home_page_redirects_anonymous_users(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("home")}'
        )

    def test_local_timezone(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Kolkata")
        self.assertTrue(settings.USE_TZ)

    def test_sqlite_connection(self):
        self.assertEqual(connection.vendor, "sqlite")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)
