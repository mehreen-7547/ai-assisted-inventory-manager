
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', views.loginpage, name='login'),
    path('logout/', views.logoutpage, name='logout'),
    path('change-password/', views.changepassword, name='change_password'),

    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt'
        ),
        name='password_reset'
    ),

    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html'
        ),
        name='password_reset_confirm'
    ),

    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
    
    path(
        'employees/',
        views.employee_list,
        name='employee_list'
    ),

    
    path(
        'employees/create/',
        views.create_employee,
        name='create_employee'
    ),

    
    path(
        'employees/edit/<int:employee_id>/',
        views.edit_employee,
        name='edit_employee'
    ),

    
    path(
        'employees/status/<int:employee_id>/',
        views.toggle_employee_status,
        name='toggle_employee_status'
    ),

    
    path(
        'employees/resend-setup/<int:employee_id>/',
        views.resend_setup_email,
        name='resend_setup_email'
    ),





]
