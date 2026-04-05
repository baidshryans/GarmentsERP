from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from contacts.models import Documents, Ledger, LedgerRole, UserLocation
from accounting.models import Account


class AllowedRetailSerializer(ModelSerializer):
    default_country_code = serializers.SerializerMethodField()

    class Meta:
        model = UserLocation
        fields = "__all__"
        depth = 2

    def get_default_country_code(self, obj):
        if obj.default_location:
            return obj.default_location.default_country_code or 'IN'
        # Fall back to first assigned retail's code
        first = obj.location.first()
        return first.default_country_code if first else 'IN'


class _RoleField(serializers.SlugRelatedField):
    """Read-only field that returns a flat list of role codes."""
    def __init__(self, **kwargs):
        super().__init__(slug_field='role', read_only=True, many=True, **kwargs)


class LedgerBriefSerializer(serializers.ModelSerializer):
    """Compact serializer used inside the account tree."""
    roles = _RoleField(source='roles')
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = Ledger
        fields = ['id', 'ac_name', 'primary_role', 'roles']

    def get_primary_role(self, obj):
        r = obj.roles.filter(is_primary=True).first()
        if r:
            return r.role
        first = obj.roles.first()
        return first.role if first else None


class AccountSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    ledgers = LedgerBriefSerializer(source='ledger_set', many=True)

    class Meta:
        model = Account
        fields = ['id', 'name', 'code', 'parent', 'children', 'ledgers']

    def get_children(self, obj):
        return AccountSerializer(obj.children.all(), many=True).data


class LedgerDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        fields = ['id', 'ldgr', 'document', 'original_name', 'document_type', 'uploaded_at']
        read_only_fields = ['original_name', 'uploaded_at']

    def create(self, validated_data):
        file = validated_data['document']
        validated_data['original_name'] = file.name
        return super().create(validated_data)