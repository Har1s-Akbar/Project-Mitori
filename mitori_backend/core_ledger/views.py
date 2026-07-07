from django.shortcuts import render
from rest_framework import generics
from .serializers import PortfolioSerializer,PositionSerializer,LedgerTransactionSerializer
# Create your views here.
from rest_framework.permissions import IsAuthenticated
from .models import Portfolio,LedgerTransaction,Position


class PortfolioView(generics.RetrieveAPIView):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.portfolio
    
class PositionsView(generics.ListAPIView):
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Position.objects.filter(portfolio= self.request.user.portfolio)
    
class LedgerView(generics.ListAPIView):
    serializer_class= LedgerTransactionSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return LedgerTransaction.objects.filter(portfolio = self.request.user.portfolio).order_by('-time_stamp')
    