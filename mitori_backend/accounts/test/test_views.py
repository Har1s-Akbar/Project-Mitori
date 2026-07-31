from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

class JWTAuthenticationTests(APITestCase):

    def setUp(self):
        # Arrange: Setup a KYC-verified user
        self.user = User.objects.create_user(
            email="quant@example.com",
            date_of_birth="1999-01-01",
            full_name="Algo Trader",
            password="securepassword123"
        )
        self.user.is_kyc_verified = True
        self.user.save()
        
        self.login_url = reverse('token_obtain_pair') 

    # FIXED: Pointing exactly to your accounts serializer module lookup
    @patch('accounts.serializers.redis_positions_portfolio_service')
    def test_successful_login_injects_kyc_and_calls_redis(self, mock_redis_service):
        """
        Proves login succeeds, KYC is inside the JWT, and the Redis cache service is triggered.
        """
        payload = {
            "email": "quant@example.com",
            "password": "securepassword123"
        }
        
        response = self.client.post(self.login_url, payload)
        
        # 1. Assert standard DRF response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        
        # 2. Assert the Redis side-effect was executed exactly once with the UUID string
        mock_redis_service.assert_called_once_with(str(self.user.id))
        
        # 3. Decode the JWT and prove the custom claim exists
        token = AccessToken(response.data['access'])
        self.assertIn('is_kyc_verified', token.payload)
        self.assertTrue(token.payload['is_kyc_verified'])

    # FIXED: Pointing exactly to your accounts serializer module lookup
    @patch('accounts.serializers.redis_positions_portfolio_service')
    def test_failed_login_blocks_redis_call(self, mock_redis_service):
        """
        Proves bad credentials yield 401 and prevent the Redis caching service from executing.
        """
        payload = {
            "email": "quant@example.com",
            "password": "wrong_password"
        }
        
        response = self.client.post(self.login_url, payload)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # 4. Prove the side-effect was safely aborted
        mock_redis_service.assert_not_called()