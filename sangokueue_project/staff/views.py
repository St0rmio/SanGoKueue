from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('staff:staff')
        else:
            # Return an 'invalid login' error message.
            return render(request, 'login.html', { 'error': "Mauvais pseudo ou mot de passe" } ) 
    else:
        return render(request, 'login.html') 


@login_required
def logout_view(request):
    logout(request)
    return render(request, 'logout.html')


@login_required
def staff_view(request):
    return render(request, 'staff.html')
