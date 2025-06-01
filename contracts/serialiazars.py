from rest_framework import serializers
from .models import Contract

class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = [
            'id',
            'client_name',
            'owner_name',
            'start_date',
            'end_date',
            'status',
            'total_value',
            'signed_date',
            'contract_text',
        ]
