from django.urls import path
from . import views



urlpatterns = [
    path('login/', views.loginPage2, name="login"),
    path('logout/', views.logoutUser2, name="logout"),

    path('', views.client, name = 'client')
    
]
