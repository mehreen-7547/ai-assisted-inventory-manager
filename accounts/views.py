from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .models import CustomUser
from .decorators import role_required
from .forms import EmployeeCreationForm
from .utils import send_welcome_email
from django.shortcuts import get_object_or_404
from .forms import EmployeeEditForm
from django.views.decorators.http import require_POST
from smtplib import SMTPException


def loginpage(request):

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('/')

        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')

@require_POST
def logoutpage(request):
    logout(request)
    return redirect('login')

# If not logged in redirect to login_url='/login/'
@login_required(login_url='/login/')
def changepassword(request):

    # This part executes when the user click on the update password button (POST is sent then)
    if request.method == 'POST':

        # request.POST = the submitted form data, including the old and new passwords.
        form = PasswordChangeForm(request.user, request.POST)

        if form.is_valid():
            # Change the password of the existing user account and returns that user object:
            user = form.save()
             # Update the current session so user STAYS LOGGED IN after password change:
            messages.success(request, 'Password changed successfully.')
            update_session_auth_hash(request, user)
            return redirect('home')
    else:
        # This part executes when the user first visits the page 
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})


@role_required('admin')
def employee_list(request):
    employees = CustomUser.objects.filter(
        role__in=['manager', 'sales']
    ).order_by('username')

    
    return render(
        request,
        'accounts/employee_list.html',
        {
            'employees': employees,
            'edit_mode': request.GET.get('mode') == 'edit'
        }
    )




@role_required('admin')
def create_employee(request):

    if request.method == 'POST':
        form = EmployeeCreationForm(request.POST)

        if form.is_valid():
            
            employee = form.save()

            try:
                send_welcome_email(request, employee)

            except (SMTPException, OSError):
                messages.error(
                    request,
                    'Employee created, but the setup email could not '
                    'be sent. Use Resend Setup Email to try again.'
                )

            else:
                messages.success(
                    request,
                    'Employee created successfully.'
                )

            return redirect('employee_list')


    else:
        form = EmployeeCreationForm()

    return render(
        request,
        'accounts/create_employee.html',
        {'form': form}
    )



@role_required('admin')
def edit_employee(request, employee_id):

    employee = get_object_or_404(
        CustomUser,
        id=employee_id,
        role__in=['manager', 'sales']
    )

    if request.method == 'POST':
        form = EmployeeEditForm(
            request.POST,
            instance=employee
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Employee updated successfully.'
            )

            return redirect('employee_list')

    else:
        form = EmployeeEditForm(instance=employee)

    return render(
        request,
        'accounts/edit_employee.html',
        {
            'form': form,
            'employee': employee
        }
    )


@role_required('admin')
@require_POST
def toggle_employee_status(request, employee_id):

    employee = get_object_or_404(
        CustomUser,
        id=employee_id,
        role__in=['manager', 'sales']
    )

    employee.is_active = not employee.is_active
    employee.save(update_fields=['is_active'])

    if employee.is_active:
        messages.success(
            request,
            'Employee activated successfully.'
        )
    else:
        messages.success(
            request,
            'Employee deactivated successfully.'
        )

    return redirect('employee_list')



@role_required('admin')
@require_POST
def resend_setup_email(request, employee_id):

    employee = get_object_or_404(
        CustomUser,
        id=employee_id,
        role__in=['manager', 'sales']
    )

    if not employee.is_active:
        messages.error(
            request,
            'Cannot send setup email to an inactive employee.'
        )

    elif employee.has_usable_password():
        messages.error(
            request,
            'Employee has already set a password.'
        )

    else:
        try:
            send_welcome_email(request, employee)

        except (SMTPException, OSError):
            messages.error(
                request,
                'Setup email could not be sent. Please try again.'
            )

        else:
            messages.success(
                request,
                'Password setup email generated successfully.'
            )

    return redirect('employee_list')




