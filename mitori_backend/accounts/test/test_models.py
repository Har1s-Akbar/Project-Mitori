from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserModelTests(TestCase):
    
    def test_create_standard_user(self):
        """Proves standard users are created with hashed passwords and no admin rights."""
        user = User.objects.create_user(
            email="trader@example.com",
            date_of_birth="1995-05-15",
            full_name="John Doe",
            password="secure_password_123"
        )
        
        self.assertEqual(user.email, "trader@example.com")
        self.assertTrue(user.check_password("secure_password_123"))
        self.assertFalse(user.is_admin)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_kyc_verified)

    def test_create_superuser(self):
        """Proves superusers receive correct elevated booleans."""
        admin = User.objects.create_superuser(
            email="admin@example.com",
            date_of_birth="1980-01-01",
            full_name="System Admin",
            password="super_password"
        )
        
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_create_user_without_email_raises_error(self):
        """Proves the manager strictly enforces the email requirement."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(
                email="",
                date_of_birth="1995-05-15",
                full_name="No Email",
                password="password123"
            )
        self.assertEqual(str(context.exception), "Users must have an email address")