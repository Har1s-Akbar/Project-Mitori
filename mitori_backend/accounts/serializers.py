from rest_framework_simplejwt.serializers import TokenObtainPairSerializer



class CustomTokenObtain(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['email'] = user.email
        token['full_name'] = user.full_name

        return token