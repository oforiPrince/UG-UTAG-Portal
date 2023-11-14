from accounts.models import User
from import_export import resources


class UserResource(resources.ModelResource):

    class Meta:
        model = User
        import_id_fields = ["email"]
        skip_unchanged = True
        use_bulk = True