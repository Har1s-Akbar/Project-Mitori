from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
import uuid

class MyUserManager(BaseUserManager):
    def create_user(self,email, date_of_birth , full_name, identity_proff_doc=None, password=None ):
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(
            email = self.normalize_email(email),
            date_of_birth = date_of_birth,
            full_name = full_name,
            identity_proff_doc = identity_proff_doc,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name,date_of_birth,password=None):
        user = self.create_user(
            email = email,
            date_of_birth = date_of_birth,
            password=password,
            full_name = full_name
        )
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True

        user.save(using = self._db)

        return user

# Create your models here.
class MyUser(PermissionsMixin, AbstractBaseUser):
    uuid = models.UUIDField(primary_key = True, default=uuid.uuid4, editable=False)
    email = models.EmailField(verbose_name='email address', max_length=255, unique=True)
    date_of_birth = models.DateField()
    full_name = models.CharField(max_length=255)
    identity_proff_doc = models.FileField(upload_to='identity_docs/', blank=True, null=True)
    is_kyc_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)


    REQUIRED_FIELDS = ['date_of_birth', 'full_name']
    USERNAME_FIELD = 'email'

    objects = MyUserManager()
    def __str__(self):
            return self.email

        