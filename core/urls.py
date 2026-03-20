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
    path('cart/', views.cart_view, name='cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('update_item/', views.update_item, name='update_item'),
    path('quan-tri/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('quan-tri/don-hang/<int:pk>/', views.admin_order_detail, name='admin_order_detail'),
    path('quan-tri/san-pham/them/', views.admin_add_product, name='admin_add_product'),
    path('quan-tri/san-pham/sua/<int:pk>/', views.admin_edit_product, name='admin_edit_product'),
    path('quan-tri/san-pham/xoa/<int:pk>/', views.admin_delete_product, name='admin_delete_product'),
    path('quan-tri/cua-hang/them/', views.admin_add_store, name='admin_add_store'),
    path('quan-tri/cua-hang/sua/<int:pk>/', views.admin_edit_store, name='admin_edit_store'),
    path('quan-tri/cua-hang/xoa/<int:pk>/', views.admin_delete_store, name='admin_delete_store'),
    path('dang-ky/', views.register_page, name='register'),
    path('dang-nhap/', views.login_page, name='login'),
    path('dang-xuat/', views.logout_user, name='logout'),
    path('api/search/', views.search_products, name='search_products'),
]