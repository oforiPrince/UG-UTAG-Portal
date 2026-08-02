from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def MustLogin(view_func):
    """Decorator ensuring the user is authenticated.

    Compatible with function-based views, method_decorator and class-based
    views (including decorating `dispatch`). It locates the `request` object
    whether the decorated callable is a plain view or a bound method.
    """

    @wraps(view_func)
    def _wrapped(*args, **kwargs):
        # Try to obtain the request object from kwargs or args
        request = kwargs.get('request')
        if request is None:
            # Common patterns: (request, ... ) or (self, request, ...)
            if len(args) >= 2 and hasattr(args[1], 'META'):
                request = args[1]
            elif len(args) >= 1 and hasattr(args[0], 'META'):
                request = args[0]

        is_auth = False
        if request is not None and hasattr(request, 'user'):
            is_auth = bool(getattr(request.user, 'is_authenticated', False))

        if not is_auth:
            try:
                messages.warning(request, "You must be logged in to perform this action.")
            except Exception:
                # if request is None or messages fails, continue to redirect
                pass
            return redirect('accounts:login')

        return view_func(*args, **kwargs)

    return _wrapped