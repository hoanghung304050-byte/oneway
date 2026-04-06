from .models import Inventory, Store
import math

def calculate_haversine(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách giữa hai điểm trên Trái Đất (đơn vị: km)
    """
    # Bán kính Trái Đất trung bình
    R = 6371.0 

    # Chuyển đổi tọa độ từ độ (degree) sang radian
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Công thức Haversine
    a = math.sin(delta_phi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2)**2
        
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def get_nearest_stock_store(product_id, user_lat, user_lng):
    # 1. Lấy danh sách ID các cửa hàng còn hàng
    available_stores_ids = Inventory.objects.filter(
        product_id=product_id, 
        stock_quantity__gt=0
    ).values_list('store_id', flat=True)

    # 2. Lấy đối tượng Store và lọc theo giờ mở cửa
    stores = Store.objects.filter(id__in=available_stores_ids)
    
    nearest_store = None
    min_dist = float('inf')

    for store in stores:
        if store.is_open: # Chỉ hiện cửa hàng đang mở cửa
            dist = calculate_haversine(user_lat, user_lng, store.location.y, store.location.x)
            if dist < min_dist:
                min_dist = dist
                nearest_store = store
                
    return nearest_store, min_dist

def calculate_shipping_fee(distance_km):
    # Ví dụ: 5km đầu 20k, mỗi km tiếp theo 5k
    if distance_km <= 5: return 20000
    return 20000 + (distance_km - 5) * 5000