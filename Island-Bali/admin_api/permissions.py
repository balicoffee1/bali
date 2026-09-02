from rest_framework.permissions import BasePermission, SAFE_METHODS


def has_admin_role(user, roles):
    return bool(
        user and user.is_authenticated and (
            user.is_superuser or user.role in roles
        )
    )


class IsSuperAdmin(BasePermission):
    """Доступ только для владельцев (Owner) и Django Superuser."""
    def has_permission(self, request, view):
        return has_admin_role(request.user, {'owner'})


class IsAdminRole(BasePermission):
    """Доступ для администраторов (Admin) и владельцев (Owner)."""
    def has_permission(self, request, view):
        return has_admin_role(request.user, {'owner', 'admin'})


class IsModeratorRole(BasePermission):
    """Доступ для контент-менеджеров (Moderator), админов и владельцев."""
    def has_permission(self, request, view):
        return has_admin_role(request.user, {'owner', 'admin', 'moderator'})


class IsSupportRole(BasePermission):
    """Доступ для службы поддержки (Support), админов и владельцев."""
    def has_permission(self, request, view):
        return has_admin_role(request.user, {'owner', 'admin', 'support'})


class IsAnyAdminUser(BasePermission):
    """Доступ к панели для любого авторизованного сотрудника с правами."""
    def has_permission(self, request, view):
        return has_admin_role(request.user, {'owner', 'admin', 'moderator', 'support'})


class IsAdminOrReadOnly(BasePermission):
    """Любая роль панели может читать; изменять могут owner/admin."""
    def has_permission(self, request, view):
        roles = {'owner', 'admin', 'moderator', 'support'} if request.method in SAFE_METHODS else {'owner', 'admin'}
        return has_admin_role(request.user, roles)


class IsModeratorOrReadOnly(BasePermission):
    """Любая роль панели может читать; контент меняют owner/admin/moderator."""
    def has_permission(self, request, view):
        roles = {'owner', 'admin', 'moderator', 'support'} if request.method in SAFE_METHODS else {'owner', 'admin', 'moderator'}
        return has_admin_role(request.user, roles)
