from django.test import SimpleTestCase


class BasicSmokeTests(SimpleTestCase):
    def test_home_url_resolves(self):
        response = self.client.get('/')
        self.assertIn(response.status_code, {200, 302})
