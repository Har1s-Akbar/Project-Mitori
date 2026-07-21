from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core_ledger.services import redis_positions_portfolio_service
class CustomTokenObtain(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['is_kyc_verified'] = user.is_kyc_verified
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)

        redis_positions_portfolio_service(str(self.user.id))
        print(self.user.id)
        return data