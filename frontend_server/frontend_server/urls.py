from django.urls import path
from django.contrib import admin

from translator import views as translator_views

# app_name = "translator"
urlpatterns = [
    # ex: /polls/
    path('home/', translator_views.home, name='home'),
    path('process_environment/', translator_views.process_environment, name='process_environment'),
    path('update_environment/', translator_views.update_environment, name='update_environment'),    
    path('admin/', admin.site.urls),
]