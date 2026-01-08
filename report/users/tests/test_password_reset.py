from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()

class PasswordResetTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='old_password123',
            first_name='Test',
            last_name='User',
            is_active=True
        )

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse('users:password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset.html')

    def test_password_reset_confirmation(self):
        response = self.client.post(reverse('users:password_reset'), {
            'email': 'test@example.com'
        })
        # Should redirect to done page
        self.assertRedirects(response, reverse('users:password_reset_done'))
        
        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Réinitialisation', mail.outbox[0].subject)

    def test_password_reset_invalid_email(self):
        response = self.client.post(reverse('users:password_reset'), {
            'email': 'nonexistent@example.com'
        })
        # Django standard behavior is to redirect even if email doesn't exist (security)
        self.assertRedirects(response, reverse('users:password_reset_done'))
        
        # But no email should be sent
        self.assertEqual(len(mail.outbox), 0)
