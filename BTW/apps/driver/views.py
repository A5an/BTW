from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from apps.base.views import loginPage
from apps.base.views import logoutUser


def loginPage2(request):
    return loginPage(request)

def logoutUser2(request):
    return logoutUser(request)


@login_required(login_url='login')
def driver(request):
    return render(request,'driver.html')


