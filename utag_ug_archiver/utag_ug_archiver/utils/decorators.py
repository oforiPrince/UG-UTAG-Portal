from django.contrib import messages
from django.shortcuts import redirect

class MustLogin:
    def __init__(self, view_func):
        self.view_func = view_func

    def __call__(self, request, *args, **kwargs):
        # Check if the user is logged in
        if not request.user.is_authenticated:
            # Add a message for the user
            messages.warning(request, "You must be logged in to perform this action.")
            # Redirect the user to the login page
            return redirect('accounts:login')

        # Call the original view function
        return self.view_func(request, *args, **kwargs)