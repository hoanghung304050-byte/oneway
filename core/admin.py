from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from .models import Product, Store

admin.site.register(Product)

@admin.register(Store)
class StoreAdmin(LeafletGeoAdmin):
    list_display = ('name', 'address', 'phone')
    search_fields = ('name', 'address')
    
    # === TÙY CHỈNH LẠI GIAO DIỆN ADMIN ===
    fieldsets = (
        ('BƯỚC 1: THÔNG TIN CƠ BẢN', {
            'fields': ('name', 'phone', 'address'),
            'description': '<i>Vui lòng nhập đầy đủ thông tin trước khi chọn vị trí trên bản đồ.</i>'
        }),
        ('BƯỚC 2: XÁC ĐỊNH VỊ TRÍ CỬA HÀNG', {
            'fields': ('location',),
            'description': '''
                <b>Ngài có 2 cách để lưu vị trí:</b><br>
                - <b>Cách 1 (Tự động):</b> Nhập địa chỉ ở trên, sau đó bấm nút màu xanh "📍 Lấy tọa độ từ Địa chỉ".<br>
                - <b>Cách 2 (Thủ công):</b> Sử dụng công cụ hình giọt nước (Draw a marker) bên trái bản đồ để tự chấm điểm tọa độ mong muốn.
            '''
        }),
    )

    # Vẫn giữ nguyên file JS để xử lý nút bấm tự động
    class Media:
        js = ('js/admin_geocode.js',)