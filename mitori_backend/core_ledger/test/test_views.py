from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from core_ledger.models import Portfolio, Position, LedgerTransaction, TransactionType, Status
import uuid
from decimal import Decimal
from django.urls import reverse

User = get_user_model()

class LedgerAndPortfolioViewTests(APITestCase):

    def setUp(self):
        """
        The Arrange Phase: 
        This runs automatically before EVERY single test, ensuring a 
        completely pristine, isolated database state.
        """
        self.user_a = User.objects.create(id=uuid.uuid4(), email="trader1@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")
        self.portfolio_a = self.user_a.portfolio 
        
        Position.objects.create(
            portfolio=self.portfolio_a, 
            asset_symbol="APP", 
            quantity=Decimal("100.00"),
            average_entry_price=Decimal("10.00") 
        )
        
        LedgerTransaction.objects.create(
            portfolio=self.portfolio_a,
            stream_order_id=str(uuid.uuid4()),
            transaction_type=TransactionType.BUY,
            price_setteled_at=Decimal("10.00"),
            price_locked_by_user=Decimal("10.00"),
            quantity=Decimal("5.00"),
            status=Status.COMPLETED,
            asset_symbol="APP"
        )
        self.user_b = User.objects.create(id=uuid.uuid4(), email="trader2@gmail.com", date_of_birth="1999-09-08", full_name="tarder",
                                              is_kyc_verified="True")
        self.portfolio_b = self.user_b.portfolio
        
        Position.objects.create(
            portfolio=self.portfolio_b, 
            asset_symbol="TSLA", 
            quantity=Decimal("50.00"),
            average_entry_price=Decimal("15.00")
        )
        
        LedgerTransaction.objects.create(
            portfolio=self.portfolio_b,
            stream_order_id=str(uuid.uuid4()),
            transaction_type=TransactionType.SELL,
            price_setteled_at=Decimal("20.00"),
            price_locked_by_user=Decimal("20.00"),
            quantity=Decimal("10.00"),
            status=Status.COMPLETED,
            asset_symbol="TSLA"
        )
    def test_portfolio_view_unauthenticated_is_401(self):
        url = reverse('portfolio-detail')
        response = self.client.get(url) 
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_portfolio_view_authenticated_returns_own_portfolio(self):
        self.client.force_authenticate(user=self.user_a)
        
        url = reverse('portfolio-detail')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(Decimal(response.data['cash_balance']), Decimal("10000.00"))
    def test_positions_view_data_isolation(self):
        self.client.force_authenticate(user=self.user_a)
        
        url = reverse('positions-list')
        response = self.client.get(url) 
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results'] 
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['asset_symbol'], "APP") 
        self.assertEqual(Decimal(results[0]['average_entry_price']), Decimal("10.00"))

    def test_ledger_view_ordering_and_isolation(self):
        LedgerTransaction.objects.create(
            portfolio=self.portfolio_a,
            stream_order_id=str(uuid.uuid4()),
            transaction_type=TransactionType.SELL,
            price_setteled_at=Decimal("15.00"),
            price_locked_by_user=Decimal("15.00"),
            quantity=Decimal("2.00"),
            status=Status.PENDING,
            asset_symbol="APP"
        )
        
        self.client.force_authenticate(user=self.user_a)
        
        url = reverse('ledger-list')
        response = self.client.get(url) 
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        
        self.assertEqual(len(results), 2)
        
        self.assertEqual(results[0]['transaction_type'], TransactionType.SELL)
        self.assertEqual(results[1]['transaction_type'], TransactionType.BUY)

    def test_positions_and_ledger_empty_state(self):
        """
        Proves that a brand new user safely receives empty arrays, 
        preventing frontend null-reference crashes.
        """
        new_user = User.objects.create(
            id=uuid.uuid4(), email="newbie@gmail.com", 
            date_of_birth="2000-01-01", full_name="Newbie", is_kyc_verified="True"
        )
        self.client.force_authenticate(user=new_user)
        
        pos_response = self.client.get(reverse('positions-list'))
        self.assertEqual(pos_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pos_response.data['results']), 0)

        ledg_response = self.client.get(reverse('ledger-list'))
        self.assertEqual(ledg_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(ledg_response.data['results']), 0)

    def test_all_endpoints_reject_unauthenticated_users(self):
        self.client.force_authenticate(user=None) 
        
        endpoints = [
            reverse('positions-list'),
            reverse('ledger-list')
        ]
        
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ledger_is_strictly_read_only(self):
        self.client.force_authenticate(user=self.user_a)
        
        malicious_payload = {
            "transaction_type": "BUY",
            "quantity": "1000000.00",
            "asset_symbol": "BTC"
        }
        
        response = self.client.post(reverse('ledger-list'), data=malicious_payload)
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)