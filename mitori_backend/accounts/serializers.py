from rest_framework_simplejwt.serializers import TokenObtainPairSerializer



class CustomTokenObtain(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['is_kyc_verified'] = user.is_kyc_verified
        return token