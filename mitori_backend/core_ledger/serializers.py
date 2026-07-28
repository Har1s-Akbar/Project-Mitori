from rest_framework import serializers
from .models import Portfolio, Position, LedgerTransaction

class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio

        fields = ['id','user','cash_balance']

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position

        fields = ['portfolio','id','asset_symbol', 'quantity', 'average_entry_price']

class LedgerTransactionSerializer(serializers.ModelSerializer):
    class Meta:

        model = LedgerTransaction

        fields = ['portfolio','stream_order_id','transaction_type','quantity','status','asset_symbol', 'time_stamp', 'price_setteled_at', 'price_locked_by_user']
        