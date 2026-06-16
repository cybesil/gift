from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import LoginForm, RegistrationForm


def account(request):
    # already logged in — nothing to do on this page

    login_form = LoginForm()
    register_form = RegistrationForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'login':
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                user = login_form.cleaned_data['user']
                if not login_form.cleaned_data.get('remember_me'):
                    # session expires when browser closes
                    request.session.set_expiry(0)
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect(request.GET.get('next') or 'ecommerce:home')

        elif action == 'register':
            register_form = RegistrationForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                messages.success(request, "Account created! Welcome to Gift Empire.")
                return redirect('ecommerce:home')

    return render(request, 'Auth/account.html', {
        'login_form': login_form,
        'register_form': register_form,
    })


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('accounts:account')