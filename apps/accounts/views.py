from smtplib import SMTPException

from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Community, Company, Department, User, UserProfile, UserRole
from .otp import OTPError, generate_and_send_otp, resend_cooldown_remaining, verify_otp
from .permissions import IsCompanyAdmin, IsManagerOrAdmin
from .serializers import (
    CommunitySerializer,
    CompanyRegistrationSerializer,
    DepartmentSerializer,
    EmployeeRegistrationSerializer,
    NetGroveTokenObtainPairSerializer,
    ResendVerificationSerializer,
    UserProfileSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)

EMAIL_SEND_FAILURE_RESPONSE = {
    'detail': 'Could not send the verification email right now. Please try again shortly.',
}


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class CompanyRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                admin_user = serializer.save()
                generate_and_send_otp(admin_user)
        except SMTPException:
            return Response(EMAIL_SEND_FAILURE_RESPONSE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                'detail': 'Registration successful. Check your email for a 6-digit verification code.',
                'email': admin_user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class EmployeeRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmployeeRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                generate_and_send_otp(user)
        except SMTPException:
            return Response(EMAIL_SEND_FAILURE_RESPONSE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                'detail': 'Registration successful. Check your email for a 6-digit verification code.',
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        code = serializer.validated_data['code']

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({'detail': 'Invalid email or code.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_active:
            return Response({'detail': 'This account is already verified.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verify_otp(user, code)
        except OTPError as exc:
            return Response({'detail': exc.message}, status=exc.status_code)

        user.is_active = True
        user.save(update_fields=['is_active'])
        if user.role == UserRole.COMPANY_ADMIN and user.company_id:
            Company.objects.filter(id=user.company_id).update(is_active=True)

        return Response(
            {'user': UserSerializer(user).data, 'tokens': _tokens_for(user)}, status=status.HTTP_200_OK
        )


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({'detail': 'No account found with this email.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_active:
            return Response(
                {'detail': 'This account is already verified. Please log in.'}, status=status.HTTP_400_BAD_REQUEST
            )

        wait = resend_cooldown_remaining(user)
        if wait > 0:
            return Response(
                {'detail': f'Please wait {wait} more second(s) before requesting another code.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            generate_and_send_otp(user)
        except SMTPException:
            return Response(EMAIL_SEND_FAILURE_RESPONSE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'detail': 'A new verification code has been sent.'}, status=status.HTTP_200_OK)


class NetGroveTokenObtainPairView(TokenObtainPairView):
    serializer_class = NetGroveTokenObtainPairSerializer


class MeView(generics.RetrieveUpdateAPIView):
    """The logged-in user's own basic info. Role/company/department are admin-controlled, not self-service."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class MyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class DepartmentListCreateView(generics.ListCreateAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Department.objects.filter(company=self.request.user.company)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsManagerOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class DepartmentDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def get_queryset(self):
        return Department.objects.filter(company=self.request.user.company)


class CommunityListView(generics.ListAPIView):
    """Communities available in the current user's company, for scoping challenge participants."""

    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Community.objects.filter(company=self.request.user.company)


class EmployeeListView(generics.ListAPIView):
    """Company admin / manager view of employees, optionally filtered by department."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAdmin]

    def get_queryset(self):
        qs = User.objects.filter(company=self.request.user.company)
        department_id = self.request.query_params.get('department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs


class EmployeeRoleUpdateView(generics.UpdateAPIView):
    """Company admin promotes/demotes a user's role and/or reassigns their department."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyAdmin]
    http_method_names = ['patch']

    def get_queryset(self):
        return User.objects.filter(company=self.request.user.company)

    def perform_update(self, serializer):
        extra = {}
        role = self.request.data.get('role')
        if role in UserRole.values:
            extra['role'] = role
        department_id = self.request.data.get('department')
        if department_id is not None:
            extra['department_id'] = department_id or None
        serializer.save(**extra)
