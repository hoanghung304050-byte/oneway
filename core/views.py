from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from .models import Order, OrderItem, Product, Store # Nhớ import các Model vào
import json

def home(request):
    return render(request, 'core/home.html')

def about(request):
    return render(request, 'core/about.html')

def warranty(request):
    return render(request, 'core/warranty.html')

def contact(request):
    return render(request, 'core/contact.html')
def map_view(request):
    # Hàm này rất đơn giản: Khi có request gọi đến, nó sẽ render (vẽ ra) file map.html
    return render(request, 'core/map.html')
def home_view(request):
    # Lấy 4 sản phẩm mới nhất để trưng bày ngoài trang chủ cho đẹp
    products = Product.objects.all()[:4]
    
    # Gửi danh sách này ra file home.html
    return render(request, 'core/home.html', {'products': products})

def product_list(request):
    # Ở trang danh sách thì lấy toàn bộ sản phẩm
    products = Product.objects.all()
    
    return render(request, 'core/product_list.html', {'products': products})

def product_detail(request, pk):
    # Lấy sản phẩm có id = pk, nếu không tìm thấy thì báo lỗi 404
    product = get_object_or_404(Product, id=pk)
    
    # Gửi sản phẩm này ra giao diện
    return render(request, 'core/product_detail.html', {'product': product})

def cart_view(request):
    return render(request, 'core/cart.html')

def checkout_view(request):
    # Dùng tạm file cart.html hoặc ngài có thể tự tạo checkout.html tương tự
    return render(request, 'core/cart.html')
def cart_view(request):
    # Lấy đơn hàng nháp (complete=False) đầu tiên trong DB làm giỏ hàng tạm thời
    order, created = Order.objects.get_or_create(complete=False)
    
    # Lấy tất cả các món hàng nằm trong đơn hàng đó
    items = order.orderitem_set.all()
    
    # Gom dữ liệu vào một cuốn từ điển (context) để gửi ra View
    context = {
        'items': items, 
        'order': order
    }
    return render(request, 'core/cart.html', context)
def map_view(request):
    # Lấy toàn bộ cửa hàng từ CSDL
    stores = Store.objects.all()
    
    # Đóng gói dữ liệu thành mảng để gửi cho JavaScript
    stores_data = []
    for store in stores:
        stores_data.append({
            'name': store.name,
            'address': store.address,
            'phone': store.phone,
            # Trong PostGIS: location.y là Vĩ độ (lat), location.x là Kinh độ (lng)
            'lat': store.location.y,
            'lng': store.location.x
        })
    
    # Chuyển đổi list Python thành chuỗi JSON an toàn
    stores_json = json.dumps(stores_data)
    
    # Gửi gói dữ liệu này ra ngoài file map.html
    return render(request, 'core/map.html', {'stores_json': stores_json})
# Hàm mới: Xử lý khi người dùng bấm "Thêm vào giỏ"
def update_item(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    
    order, created = Order.objects.get_or_create(complete=False)
    product = Product.objects.get(id=productId)
    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
    
    # Nếu hành động là thêm (add)
    if action == 'add':
        orderItem.quantity = (orderItem.quantity + 1)
        orderItem.save()
        
    # Nếu hành động là giảm bớt 1 cái (remove) - Trẫm viết sẵn cho ngài luôn
    elif action == 'remove':
        orderItem.quantity = (orderItem.quantity - 1)
        orderItem.save()
    
    # NẾU HÀNH ĐỘNG LÀ XÓA HẲN (delete) HOẶC SỐ LƯỢNG TỤT XUỐNG 0
    if action == 'delete' or orderItem.quantity <= 0:
        orderItem.delete() # Xóa sổ khỏi Database
    
    return JsonResponse('Đã cập nhật giỏ hàng thành công!', safe=False)