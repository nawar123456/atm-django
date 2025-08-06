# views.py

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404

# --- النماذج ---
from .models import User, CardDetail, Transaction, DeliveryLocation, DeliverySchedule, DigitalSignature, Employee

# --- السيريالايزر ---
from .serializers import (
    UserSerializer,
    CardDetailSerializer,
    TransactionSerializer,
    TransferTransactionSerializer,
    DeliveryLocationSerializer,
    DeliveryScheduleSerializer,
    EmployeeSerializer,
)

# --- الصلاحيات المخصصة ---
from .permissions import IsAdminUser, IsApprovedUser


# ================================
# 1. تسجيل الدخول
# ================================
class LoginView(APIView):
    """
    تسجيل الدخول وإصدار JWT tokens.
    """
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "البريد الإلكتروني وكلمة المرور مطلوبان"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(email=email, password=password)
        if not user:
            return Response(
                {"error": "البريد الإلكتروني أو كلمة المرور غير صحيحة"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'status': user.status,
                'is_approved': user.is_approved,
                'full_name': user.get_full_name() or user.username
            }
        })


# ================================
# 2. إدارة المستخدمين (للإدارة فقط)
# ================================
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    عرض المستخدمين (فقط للمدراء).
    لا يُعرض أي حقل حساس (مثل كلمة المرور).
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        # فقط الحقول العامة
        return User.objects.only(
            'id', 'first_name', 'last_name', 'email', 'status',
            'phone_number', 'emirates_id', 'passport', 'birth_date'
        )

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
        user = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(User.STATUS_CHOICES).keys():
            return Response(
                {'error': 'الحالة غير صالحة'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.status = new_status
        user.save(update_fields=['status'])
        return Response({'status': f'تم تحديث الحالة إلى {new_status}'})


# ================================
# 3. إدارة البطاقات
# ================================
class CardDetailViewSet(viewsets.ModelViewSet):
    """
    إدارة بطاقات المستخدم (عرض فقط، لا إنشاء).
    """
    serializer_class = CardDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CardDetail.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # لا يُسمح بإنشاء بطاقة مباشرة
        raise PermissionError("لا يمكن إضافة بطاقة من خلال هذه الواجهة. استخدم نظام الدفع الخارجي.")


# ================================
# 4. المعاملات
# ================================
class TransactionViewSet(viewsets.ModelViewSet):
    """
    إدارة المعاملات (سحب، إيداع، تحويل).
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsApprovedUser]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def start(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ================================
# 5. التحويلات بين المستخدمين
# ================================
class TransferTransactionViewSet(viewsets.ModelViewSet):
    """
    تحويل الأموال بين المستخدمين.
    """
    serializer_class = TransferTransactionSerializer
    permission_classes = [IsApprovedUser]

    def get_queryset(self):
        return TransferTransaction.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ================================
# 6. إدارة الموظفين (فقط للمدراء)
# ================================
class EmployeeCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get('user_id')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        role = request.data.get('role')

        if not all([user_id, first_name, last_name, role]):
            return Response(
                {"error": "جميع الحقول مطلوبة: user_id, first_name, last_name, role"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "المستخدم غير موجود"}, status=404)

        if hasattr(user, 'employee_profile'):
            return Response({"error": "هذا المستخدم موظف بالفعل"}, status=400)

        employee = Employee.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        return Response({
            "message": "تم إنشاء الموظف بنجاح",
            "data": EmployeeSerializer(employee).data
        }, status=status.HTTP_201_CREATED)


class EmployeeUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "تم تحديث الموظف بنجاح",
                "data": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmployeeListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        employees = Employee.objects.select_related('user').all()
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmployeeDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        employee.delete()
        return Response(
            {"message": "تم حذف الموظف بنجاح"},
            status=status.HTTP_204_NO_CONTENT
        )


# ================================
# 7. التحقق من الهوية (وجه + هوية)
# ================================
class FaceIDVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        face_scan = request.data.get("face_scan")
        emirates_id = request.data.get("emirates_id")

        if not face_scan or not emirates_id:
            return Response(
                {"error": "الرجاء رفع صورة الوجه وهوية الإمارات"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user.face_scan = face_scan
        user.emirates_id = emirates_id
        user.status = 'pending'  # الانتظار للمراجعة
        user.save(update_fields=['face_scan', 'emirates_id', 'status'])

        return Response({
            "message": "تم رفع بيانات التحقق. سيتم مراجعتها من قبل الإدارة."
        }, status=status.HTTP_200_OK)


# ================================
# 8. التوقيع الرقمي
# ================================
class SignatureView(APIView):
    permission_classes = [IsApprovedUser]

    def post(self, request):
        signature_data = request.data.get("signature_data")
        if not signature_data:
            return Response(
                {"error": "الرجاء إرسال بيانات التوقيع"},
                status=status.HTTP_400_BAD_REQUEST
            )

        DigitalSignature.objects.update_or_create(
            user=request.user,
            defaults={"signature_data": signature_data}
        )
        return Response({"message": "تم حفظ التوقيع الرقمي بنجاح"}, status=status.HTTP_200_OK)


# ================================
# 9. التسليم والموقع (Delivery)
# ================================
class DeliveryLocationViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryLocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeliveryLocation.objects.filter(transaction__user=self.request.user)


class DeliveryScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeliverySchedule.objects.filter(transaction__user=self.request.user)