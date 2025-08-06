from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'cards', CardDetailViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'transfers', TransferTransactionViewSet)
router.register(r'delivery-locations', DeliveryLocationViewSet)
router.register(r'delivery-schedules', DeliveryScheduleViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    path('employees/create/', EmployeeCreateView.as_view(), name='employee-create'),
    path('employees/update/<int:pk>/', EmployeeUpdateView.as_view(), name='employee-update'),
    path('employees/all/', EmployeeListView.as_view(), name='employee-list'),
    path('employees/delete/<int:pk>/', EmployeeDeleteView.as_view(), name='employee-delete'),
    path('delivery/payment/', PaymentView.as_view(), name='payment'),
    path('delivery/verify-face-id/', FaceIDVerificationView.as_view(), name='verify-face-id'),
    path('delivery/signature/', SignatureView.as_view(), name='digital-signature'),
]
