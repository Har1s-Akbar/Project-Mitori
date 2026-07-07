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

        fields = ['portfolio','id','transaction_type','amount','status','asset_symbol', 'time_stamp']
        read_only_fields=['id','time_stamp','status']

        def validate(self,data):
            transaction_type = data.transaction_type
            amount = data.amount

            request = self.context.get('request')
            portfolio = request.user.portfolio

            if transaction_type == 'BUY':
                if portfolio.cash_balance < amount:
                    raise serializers.ValidationError("Insufficient trades for this fund")
                return data