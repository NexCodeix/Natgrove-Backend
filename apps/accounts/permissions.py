from rest_framework.permissions import BasePermission

from .models import UserRole


class IsCompanyAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.COMPANY_ADMIN)


class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.COMPANY_ADMIN, UserRole.MANAGER)
        )


class IsSameCompany(BasePermission):
    """Object-level check: the target object's company must match the requesting user's company."""

    def has_object_permission(self, request, view, obj):
        company = getattr(obj, 'company', obj if obj.__class__.__name__ == 'Company' else None)
        return bool(request.user.company_id and company and company.id == request.user.company_id)
