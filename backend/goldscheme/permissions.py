from rest_framework.permissions import BasePermission


class SchemeEnrollmentAccessPermission(BasePermission):
    """
    Object-level guard: the enrollment must belong to the retail tied to
    the current request. Defence-in-depth alongside RetailBaseViewset's
    queryset filter — survives any future viewset that forgets to scope.
    """

    def has_object_permission(self, request, view, obj):
        retail = getattr(request, "retail", None)
        if retail is None:
            return False
        return obj.retail_id == retail.id
