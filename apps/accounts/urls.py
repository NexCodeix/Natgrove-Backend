from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path('register/company/', views.CompanyRegistrationView.as_view(), name='register-company'),
    path('register/employee/', views.EmployeeRegistrationView.as_view(), name='register-employee'),
    path('login/', views.NetGroveTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    path('me/', views.MeView.as_view(), name='me'),
    path('me/profile/', views.MyProfileView.as_view(), name='my-profile'),

    path('departments/', views.DepartmentListCreateView.as_view(), name='department-list-create'),
    path('departments/<uuid:pk>/', views.DepartmentDetailView.as_view(), name='department-detail'),

    path('communities/', views.CommunityListView.as_view(), name='community-list'),

    path('employees/', views.EmployeeListView.as_view(), name='employee-list'),
    path('employees/<uuid:pk>/role/', views.EmployeeRoleUpdateView.as_view(), name='employee-role-update'),
]
