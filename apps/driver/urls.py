from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.loginPage2, name="login"),
    path('logout/', views.logoutUser2, name="logout"),

    path('', views.driver,  name = 'driver'),
    path('create-lobby/',views.create_lobby, name = 'create-lobby')
]