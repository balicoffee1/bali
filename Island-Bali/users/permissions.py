from rest_framework.permissions import BasePermission


class CustomPermission(BasePermission):
    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles

    def has_permission(self, request, view):
        user = request.user
        if user.role:
            return user.role in self.allowed_roles
        return False


class CanViewOrders(CustomPermission):
    def __init__(self):
        super().__init__(["user"])


class CanCreateGoal(CustomPermission):
    def __init__(self):
        super().__init__(["owner", "admin"])


class CanEditGoal(CustomPermission):
    def __init__(self):
        super().__init__(["owner", "admin"])


class OwnerPermission(CustomPermission):
    def __init__(self):
        super().__init__(["owner"])
