from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'), # Đường dẫn trống '' là trang chủ
    path('gioi-thieu/', views.about, name='about'),
    path('bao-hanh/', views.warranty, name='warranty'),
    path('lien-he/', views.contact, name='contact'),
    path('map/', views.map_view, name='map_view'),
    path('products/', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart_view'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('update_item/', views.update_item, name='update_item'),
]