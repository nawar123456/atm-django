from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'employee_profile') and
            request.user.employee_profile.role == 'admin'
        )

class IsApprovedUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.status == 'verified'