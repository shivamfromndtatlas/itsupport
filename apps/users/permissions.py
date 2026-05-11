from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Allow access only to super_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'super_admin'
        )


class IsHROrSuperAdmin(BasePermission):
    """Allow access to hr or super_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('hr', 'super_admin')
        )


class IsITSpecialistOrSuperAdmin(BasePermission):
    """Allow access to it_specialist or super_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('it_specialist', 'super_admin')
        )


class IsITOrHROrSuperAdmin(BasePermission):
    """Allow access to it_specialist, hr, or super_admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('it_specialist', 'hr', 'super_admin')
        )
