from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import MyUser

class CustomAdmin(UserAdmin):
    model = MyUser

    ordering = ['email']


    list_display =['email','date_of_birth', 'full_name','is_staff','is_admin','is_kyc_verified']

    search_fields =['email']

    fieldsets =(
        ('login Credentials', {'fields':('email', 'password')}),
        ('permissions',{'fields':('is_staff', 'is_active','is_superuser')})
    )

admin.site.register(MyUser,CustomAdmin)

# Register your models here.
