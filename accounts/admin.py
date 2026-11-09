
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import EmployeeCreationForm
from .utils import send_welcome_email


class CustomUserAdmin(UserAdmin):

    add_form = EmployeeCreationForm

    fieldsets = UserAdmin.fieldsets + (
        ('Inventory Role', {'fields': ('role',)}),
    )

    add_fieldsets = (
        (None, {
            'fields': (
                'username',
                'first_name',
                'last_name',
                'email',
                'role'
            )
        }),
    )

    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change:
            send_welcome_email(request, obj)

    
    actions = ['resend_setup_email']

    @admin.action(description='Resend password setup email')
    def resend_setup_email(self, request, queryset):
        count = 0

        for user in queryset:
            if user.is_active and not user.has_usable_password() and user.email:
                send_welcome_email(request, user)
                count += 1

        self.message_user(
            request,
            f'Setup email generated for {count} employee(s).'
        )
   


admin.site.register(CustomUser, CustomUserAdmin)
