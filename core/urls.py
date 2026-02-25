from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'), # Đường dẫn trống '' là trang chủ
    path('gioi-thieu/', views.about, name='about'),
    path('bao-hanh/', views.warranty, name='warranty'),
    path('lien-he/', views.contact, name='contact'),
]