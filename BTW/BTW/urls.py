
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.base.urls')),
    path('client/',include('apps.client.urls')),
    path('driver/',include('apps.driver.urls')),
    
]
