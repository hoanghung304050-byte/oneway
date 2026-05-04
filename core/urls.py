from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path
from django.views.static import serve
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('gioi-thieu/', views.about, name='about'),
    path('quan-tri/manage-about/', views.manage_about, name='manage_about'),
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
    path('dang-ky/', views.register, name='register'),
    path('dang-nhap/', views.login_page, name='login'),
    path('dang-xuat/', views.logout_user, name='logout'),
    path('api/search/', views.search_products, name='search_products'),
    path('quan-tri/toggle-staff/<int:user_id>/', views.toggle_user_staff, name='toggle_user_staff'),
    path('quan-tri/delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('quan-tri/change-role/<int:user_id>/<str:role>/', views.change_user_role, name='change_user_role'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('store/<int:store_id>/', views.store_detail, name='store_detail'),
    path('quan-tri/dieu-dong/', views.transfer_manager, name='transfer_manager'),
    path('quan-tri/cap-nhat-kho/', views.update_stock, name='update_stock'),
    path('quen-mat-khau/', views.forgot_password_otp, name='forgot_password_otp'),
    path('xac-nhan-otp-quen-mk/', views.verify_forgot_otp, name='verify_forgot_otp'),
    path('dat-lai-mk/', views.set_new_password, name='set_new_password'),
    path('quan-ly-kho/', views.import_inventory_excel, name='inventory_management'),
    path('xuat-kho-excel/', views.export_inventory_excel, name='export_inventory_excel'),
    path('product/<int:product_id>/review/', views.submit_review, name='submit_review'),
    path('upload-editor-image/', views.upload_editor_image, name='upload_editor_image'),
]

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)