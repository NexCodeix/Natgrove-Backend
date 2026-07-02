from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.core.models import BaseModel


class UserRole(models.TextChoices):
    COMPANY_ADMIN = 'COMPANY_ADMIN', 'Company Admin'
    MANAGER = 'MANAGER', 'Manager'
    EMPLOYEE = 'EMPLOYEE', 'Employee'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.COMPANY_ADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.EMPLOYEE)
    company = models.ForeignKey(
        'accounts.Company', null=True, blank=True, on_delete=models.SET_NULL, related_name='employees'
    )
    department = models.ForeignKey(
        'accounts.Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='members'
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.username


class Company(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    email_domain = models.CharField(
        max_length=255,
        unique=True,
        help_text="Employees may only self-register with an email ending in this domain, e.g. 'acme.com'.",
    )
    admin = models.OneToOneField(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='administered_company'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Department(BaseModel):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=255)
    manager = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments'
    )

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class UserProfile(BaseModel):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)

    def __str__(self):
        return f'Profile of {self.user.email}'
