from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User  # أو import get_user_model()

admin.site.register(User, UserAdmin)