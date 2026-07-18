from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtain

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtain