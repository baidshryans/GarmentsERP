from rest_framework.serializers import ModelSerializer

from goldrates.models import GoldRates, PurityMaster

class PurityMasterSerializer(ModelSerializer):
    class Meta:
        model = PurityMaster
        fields = "__all__"

class GoldRatesSerializer(ModelSerializer):
    class Meta:
        model = GoldRates
        fields = ['purity_name','date1','purity','rate']
        extra_kwargs = {
            'purity_name': {'read_only': True}
        }