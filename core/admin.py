from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin  # Import thư viện Admin của Leaflet
from .models import Product, Store

# Đăng ký bảng Product
admin.site.register(Product)

# Đăng ký bảng Store bằng LeafletGeoAdmin
@admin.register(Store)
class StoreAdmin(LeafletGeoAdmin):
    list_display = ('name', 'address', 'phone')
    search_fields = ('name', 'address')