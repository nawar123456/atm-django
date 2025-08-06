from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import RegexValidator
from django.utils import timezone


# --- الإمارات ID Validator ---
UAE_ID_REGEX = r'^\d{3}-\d{4}-\d{7}-\d{1}$'
emirates_id_validator = RegexValidator(
    regex=UAE_ID_REGEX,
    message="يجب أن يكون الهوية الإماراتية بالصيغة: 784-1995-1234567-1"
)


from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import RegexValidator
from django.utils import timezone


# --- الإمارات ID Validator ---
UAE_ID_REGEX = r'^\d{3}-\d{4}-\d{7}-\d{1}$'
emirates_id_validator = RegexValidator(
    regex=UAE_ID_REGEX,
    message="يجب أن يكون الهوية الإماراتية بالصيغة: 784-1995-1234567-1"
)


# --- النموذج الرئيسي: User ---
class User(AbstractUser):
    email = models.EmailField(unique=True)
    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    # تخزين الصور (لا تُخزن كـ text)
    face_scan = models.ImageField(upload_to='face_scans/', null=True, blank=True)

    # تحسين الحقول مع التحقق من التنسيق
    emirates_id = models.CharField(
        max_length=19,
        null=True,
        blank=True,
        validators=[emirates_id_validator]
    )
    passport = models.CharField(max_length=15, unique=True, null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('blocked', 'Blocked'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # التأكد من أن الصلاحيات معرّفة بشكل صحيح
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_set',
        blank=True,
    )

    # التحكم في الدخول بناءً على الحالة
    @property
    def is_active(self):
        return self.status == 'verified'

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email


# --- موظف النظام (يرتبط بـ User) ---
class Employee(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.title()}"


# --- تفاصيل البطاقة (بدون CVV!) ---
class CardDetail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cards')
    
    # لا تُخزن الأرقام الكاملة! فقط آخر 4 أرقام
    last_four = models.CharField(max_length=4)  # مثلاً: "4242"
    expiry = models.CharField(max_length=5)    # "MM/YY"
    cardholder_name = models.CharField(max_length=100)
    
    # رقم داخلي من نظام الدفع (مثل Stripe ID) - لا يُستخدم في المعاملات
    payment_method_id = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Card ending in {self.last_four}"


# --- المعاملة المالية (Transaction) ---
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('withdrawal', 'Withdrawal'),
        ('deposit', 'Deposit'),
        ('send_money', 'Send Money'),
        ('receive_money', 'Receive Money'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    card = models.ForeignKey(CardDetail, on_delete=models.SET_NULL, null=True, related_name='transactions')
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # دعم أرقام أكبر
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(default=timezone.now)

    currency_from = models.CharField(max_length=3, default='AED')
    currency_to = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    # المستلم (لتحويل الأموال)
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transactions'
    )

    # رسالة للمستلم
    message_to_recipient = models.TextField(blank=True, null=True)

    # توقيت التحديث
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} {self.currency_from}"


# --- موقع التسليم ---
class DeliveryLocation(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='delivery_locations')
    
    is_current_location = models.BooleanField(default=False)
    building_type = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.TextField()

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Location for {self.transaction}"


# --- جدول التسليم ---
class DeliverySchedule(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='delivery_schedules')
    delivery_type = models.CharField(max_length=50)  # مثل: "same_day", "scheduled"
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.delivery_type} on {self.scheduled_date}"


# --- التوقيع الرقمي ---
class DigitalSignature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    
    # يمكن أن يكون صورة أو SVG أو بيانات base64
    signature_data = models.TextField()  # SVG أو base64
    signed_at = models.DateTimeField(default=timezone.now)
    
    PURPOSE_CHOICES = [
        ('transfer', 'Transfer'),
        ('delivery', 'Delivery'),
        ('verification', 'Verification'),
    ]
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)

    def __str__(self):
        return f"Signature by {self.user.email} for {self.purpose}"
# --- موظف النظام (يرتبط بـ User) ---
class Employee(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.title()}"


# --- تفاصيل البطاقة (بدون CVV!) ---
class CardDetail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cards')
    
    # لا تُخزن الأرقام الكاملة! فقط آخر 4 أرقام
    last_four = models.CharField(max_length=4)  # مثلاً: "4242"
    expiry = models.CharField(max_length=5)    # "MM/YY"
    cardholder_name = models.CharField(max_length=100)
    
    # رقم داخلي من نظام الدفع (مثل Stripe ID) - لا يُستخدم في المعاملات
    payment_method_id = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Card ending in {self.last_four}"


# --- المعاملة المالية (Transaction) ---
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('withdrawal', 'Withdrawal'),
        ('deposit', 'Deposit'),
        ('send_money', 'Send Money'),
        ('receive_money', 'Receive Money'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    card = models.ForeignKey(CardDetail, on_delete=models.SET_NULL, null=True, related_name='transactions')
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # دعم أرقام أكبر
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(default=timezone.now)

    currency_from = models.CharField(max_length=3, default='AED')
    currency_to = models.CharField(max_length=3, default='USD')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    # المستلم (لتحويل الأموال)
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transactions'
    )

    # رسالة للمستلم
    message_to_recipient = models.TextField(blank=True, null=True)

    # توقيت التحديث
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} {self.currency_from}"


# --- موقع التسليم ---
class DeliveryLocation(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='delivery_locations')
    
    is_current_location = models.BooleanField(default=False)
    building_type = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.TextField()

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Location for {self.transaction}"


# --- جدول التسليم ---
class DeliverySchedule(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='delivery_schedules')
    delivery_type = models.CharField(max_length=50)  # مثل: "same_day", "scheduled"
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.delivery_type} on {self.scheduled_date}"


# --- التوقيع الرقمي ---
class DigitalSignature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    
    # يمكن أن يكون صورة أو SVG أو بيانات base64
    signature_data = models.TextField()  # SVG أو base64
    signed_at = models.DateTimeField(default=timezone.now)
    
    PURPOSE_CHOICES = [
        ('transfer', 'Transfer'),
        ('delivery', 'Delivery'),
        ('verification', 'Verification'),
    ]
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)

    def __str__(self):
        return f"Signature by {self.user.email} for {self.purpose}"