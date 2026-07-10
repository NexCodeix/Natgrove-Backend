from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Community, Company, Department, User, UserProfile, UserRole, generate_unique_username


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name',
            'role', 'company', 'department', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'username', 'role', 'company', 'department', 'is_active', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'bio', 'profile_image']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'description', 'logo', 'email_domain', 'admin', 'is_active', 'created_at']
        read_only_fields = ['id', 'admin', 'is_active', 'created_at']


class CommunitySerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ['id', 'company', 'scope', 'department', 'name', 'member_count']

    def get_member_count(self, obj):
        return obj.member_queryset().count()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'company', 'name', 'manager']
        read_only_fields = ['id', 'company']


class CompanyRegistrationSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    email_domain = serializers.CharField(max_length=255)

    admin_full_name = serializers.CharField(max_length=255)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate_email_domain(self, value):
        value = value.lower().lstrip('@')
        if Company.objects.filter(email_domain=value).exists():
            raise serializers.ValidationError('A company with this email domain is already registered.')
        return value

    def validate_admin_email(self, value):
        value = value.lower()
        if not value.split('@')[-1] == self.initial_data.get('email_domain', '').lower().lstrip('@'):
            raise serializers.ValidationError('Admin email must belong to the company email domain.')
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        if attrs['admin_password'] != attrs.pop('admin_confirm_password'):
            raise serializers.ValidationError({'admin_confirm_password': 'Passwords do not match.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        admin_user = User.objects.create_user(
            email=validated_data['admin_email'],
            username=generate_unique_username(validated_data['admin_email']),
            password=validated_data['admin_password'],
            full_name=validated_data['admin_full_name'],
            role=UserRole.COMPANY_ADMIN,
            is_active=False,
        )
        company = Company.objects.create(
            name=validated_data['company_name'],
            description=validated_data.get('description', ''),
            email_domain=validated_data['email_domain'],
            admin=admin_user,
            is_active=False,
        )
        admin_user.company = company
        admin_user.save(update_fields=['company'])
        UserProfile.objects.create(user=admin_user)
        return admin_user


class EmployeeRegistrationSerializer(serializers.Serializer):
    """
    Employees only ever provide their normal work email - the company is
    looked up from the email's domain, not passed in by the client. There is
    no way for an employee to know their company's internal id up front.
    """

    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        email = attrs['email'].lower()
        email_domain = email.split('@')[-1]
        try:
            company = Company.objects.get(email_domain=email_domain, is_active=True)
        except Company.DoesNotExist:
            raise serializers.ValidationError(
                {'email': f"No verified company is registered with the '{email_domain}' email domain."}
            )
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})

        attrs['email'] = email
        attrs['company'] = company
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=generate_unique_username(validated_data['email']),
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            role=UserRole.EMPLOYEE,
            company=validated_data['company'],
            is_active=False,
        )
        UserProfile.objects.create(user=user)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=4)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class NetGroveTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['company_id'] = str(user.company_id) if user.company_id else None
        return token

    def validate(self, attrs):
        email = attrs.get(self.username_field, '')
        password = attrs.get('password', '')
        pending_user = User.objects.filter(email__iexact=email, is_active=False).first()
        if pending_user and pending_user.check_password(password):
            # AuthenticationFailed stringifies every value in a dict detail (DRF's
            # _get_error_details calls force_str on leaves), so a boolean flag here
            # would silently become the string "True"/"False" - the `code` field is
            # what frontends should branch on instead.
            raise AuthenticationFailed(
                {'detail': 'Please verify your email before logging in.'}, code='email_not_verified'
            )

        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
