from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles=[]):
    """
    Decorator for views that checks whether the logged in user has one of the allowed roles.
    Also ensures locked users cannot access protected views.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if getattr(request.user, 'is_locked', False):
                logout(request)
                messages.error(request, "Your account has been locked by an administrator.")
                return redirect('login')

            # Superusers always have full access
            if request.user.is_superuser or request.user.role == 'SUPERUSER':
                return view_func(request, *args, **kwargs)

            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, "You do not have permission to access this page.")
            return redirect('dashboard')

        return _wrapped_view
    return decorator


class RoleRequiredMixin:
    """
    Mixin for Class-Based Views to enforce role requirements.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if getattr(request.user, 'is_locked', False):
            logout(request)
            messages.error(request, "Your account has been locked by an administrator.")
            return redirect('login')

        if request.user.is_superuser or request.user.role == 'SUPERUSER':
            return super().dispatch(request, *args, **kwargs)

        if request.user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)

        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard')
