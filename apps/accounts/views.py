from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Department, User, UserProfile, UserRole
from .permissions import IsCompanyAdmin, IsManagerOrAdmin
from .serializers import (
    CompanyRegistrationSerializer,
    DepartmentSerializer,
    EmployeeRegistrationSerializer,
    NetGroveTokenObtainPairSerializer,
    UserProfileSerializer,
    UserSerializer,
)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class CompanyRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_user = serializer.save()
        return Response(
            {'user': UserSerializer(admin_user).data, 'tokens': _tokens_for(admin_user)},
            status=status.HTTP_201_CREATED,
        )


class EmployeeRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmployeeRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, 'tokens': _tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


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
