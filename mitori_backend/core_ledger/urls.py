from django.urls import path
from .views import PortfolioView, LedgerView, PositionsView

urlpatterns = [
    path('portfolio/', PortfolioView.as_view(), name='portfolio-detail'),
    path('transactions/', LedgerView.as_view(), name='ledger-list'),
    path('positions/', PositionsView.as_view(), name='positions-list')
]