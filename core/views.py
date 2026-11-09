from django.shortcuts import render
from accounts.decorators import role_required


@role_required('admin', 'manager', 'sales')
def home(request):
    return render(request, 'core/home.html')