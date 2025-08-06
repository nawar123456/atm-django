from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import User, CardDetail, Transaction, DeliveryLocation, DeliverySchedule, Employee, TransferTransaction

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'email', 'password', 'phone_number', 'birth_date', 'emirates_id', 'passport', 'status']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CardDetailSerializer(serializers.ModelSerializer):
    last_four = serializers.CharField(read_only=True)
    expiry = serializers.CharField(read_only=True)
    cardholder_name = serializers.CharField(read_only=True)

    class Meta:
        model = CardDetail
        fields = ['id', 'last_four', 'expiry', 'cardholder_name']


class DeliveryLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryLocation
        fields = ['is_current_location', 'building_type', 'latitude', 'longitude', 'address']


class DeliveryScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySchedule
        fields = ['delivery_type', 'scheduled_date', 'scheduled_time']


class TransactionSerializer(serializers.ModelSerializer):
    delivery_locations = DeliveryLocationSerializer(many=True, required=False)
    delivery_schedules = DeliveryScheduleSerializer(many=True, required=False)
    card_id = serializers.PrimaryKeyRelatedField(
        queryset=CardDetail.objects.all(),
        write_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            'transaction_type', 'amount', 'currency_from', 'currency_to',
            'card_id', 'delivery_locations', 'delivery_schedules'
        ]

    def create(self, validated_data):
        locations_data = validated_data.pop('delivery_locations', [])
        schedules_data = validated_data.pop('delivery_schedules', [])
        card_id = validated_data.pop('card_id')
        user = self.context['request'].user

        if card_id.user != user:
            raise serializers.ValidationError("البطاقة لا تخصك.")

        transaction = Transaction.objects.create(
            user=user,
            card=card_id,
            **validated_data
        )

        for loc_data in locations_data:
            DeliveryLocation.objects.create(transaction=transaction, **loc_data)

        for sched_data in schedules_data:
            DeliverySchedule.objects.create(transaction=transaction, **sched_data)

        return transaction


class TransferTransactionSerializer(serializers.ModelSerializer):
    recipient_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TransferTransaction
        fields = [
            'transaction_type', 'recipient_id', 'amount_sent',
            'currency_sent', 'amount_received', 'currency_received',
            'message_to_recipient', 'location'
        ]

    def create(self, validated_data):
        recipient_id = validated_data.pop('recipient_id')
        user = self.context['request'].user

        try:
            recipient = User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("المستخدم غير موجود.")

        validated_data['user'] = user
        validated_data['recipient'] = recipient
        return super().create(validated_data)


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['id', 'first_name', 'last_name', 'role']
        read_only_fields = ['role']