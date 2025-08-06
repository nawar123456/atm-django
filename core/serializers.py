# serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import User, CardDetail, Transaction, DeliveryLocation, DeliverySchedule, Employee

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'username', 'email',
            'password', 'phone_number', 'birth_date', 'emirates_id',
            'passport', 'status'
        ]

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
    recipient_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Transaction
        fields = [
            'transaction_type',
            'amount',
            'currency_from',
            'currency_to',
            'card_id',
            'recipient_id',
            'message_to_recipient',
            'delivery_locations',
            'delivery_schedules'
        ]

    def create(self, validated_data):
        # استخراج الحقول الإضافية
        locations_data = validated_data.pop('delivery_locations', [])
        schedules_data = validated_data.pop('delivery_schedules', [])
        card_id = validated_data.pop('card_id')
        recipient_id = validated_data.pop('recipient_id', None)
        user = self.context['request'].user

        # التحقق من أن البطاقة تخص المستخدم
        if card_id.user != user:
            raise serializers.ValidationError("البطاقة لا تخصك.")

        # التحقق من أن المستلم موجود (إذا كان نوع المعاملة تحويل)
        recipient = None
        if validated_data['transaction_type'] in ['send_money', 'receive_money']:
            if not recipient_id:
                raise serializers.ValidationError("حقل 'recipient_id' مطلوب للتحويلات.")
            try:
                recipient = User.objects.get(id=recipient_id)
            except User.DoesNotExist:
                raise serializers.ValidationError("المستخدم المستلم غير موجود.")

        # إنشاء المعاملة
        transaction = Transaction.objects.create(
            user=user,
            card=card_id,
            recipient=recipient,
            **validated_data
        )

        # إنشاء مواقع التسليم
        for loc_data in locations_data:
            DeliveryLocation.objects.create(transaction=transaction, **loc_data)

        # إنشاء جداول التسليم
        for sched_data in schedules_data:
            DeliverySchedule.objects.create(transaction=transaction, **sched_data)

        return transaction
