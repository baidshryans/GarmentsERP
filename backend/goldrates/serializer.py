from rest_framework.serializers import ModelSerializer

from goldrates.models import GoldRates, PurityMaster

class PurityMasterSerializer(ModelSerializer):
    class Meta:
        model = PurityMaster
        fields = "__all__"

class GoldRatesSerializer(ModelSerializer):
    class Meta:
        model = GoldRates
        fields = ['purity_name','date1','purity','rate','buying_rate','selling_rate']
        extra_kwargs = {
            'purity_name': {'read_only': True},
            'rate': {'required': False},
        }

    def validate(self, attrs):
        # Mirror selling_rate into legacy `rate` if rate not provided
        if not attrs.get('rate'):
            attrs['rate'] = attrs.get('selling_rate') or attrs.get('buying_rate') or 0
        return attrs