
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F, Count
from .forms import ProductForm, StoreForm
from .models import Order, OrderItem, Product, Store, Review
import json

# === 1. CÁC TRANG CƠ BẢN ===
def home(request):
    return render(request, 'core/home.html')

def about(request):
    return render(request, 'core/about.html')

def warranty(request):
    return render(request, 'core/warranty.html')

def contact(request):
    return render(request, 'core/contact.html')

def home_view(request):
    products = Product.objects.all()
    return render(request, 'core/home.html', {'products': products})

def product_list(request):
    # 1. Lấy danh sách các thương hiệu khách đã tích (trả về một list ['iphone', 'samsung',...])
    selected_brands = request.GET.getlist('brands')
    
    # 2. Bắt đầu với tất cả sản phẩm
    products = Product.objects.all()

    # 3. Nếu khách có tích vào ít nhất 1 ô, tiến hành lọc "tất cả trong một"
    if selected_brands:
        # Lọc những sản phẩm có tên chứa bất kỳ thương hiệu nào trong danh sách
        # Chúng ta dùng Q object để tạo truy vấn "OR" phức tạp hơn một chút
        from django.db.models import Q
        query = Q()
        for brand in selected_brands:
            query |= Q(name__icontains=brand) # |= tương đương với phép OR
        products = products.filter(query)

    context = {
        'products': products,
        'selected_brands': selected_brands, # Gửi ngược lại để giữ trạng thái đã tích
    }
    return render(request, 'core/product_list.html', context)

def product_detail(request, pk):
    product = get_object_or_404(Product, id=pk)
    # Lấy toàn bộ đánh giá của sản phẩm này, cái nào mới nhất đưa lên đầu
    reviews = product.review_set.all().order_by('-created_at')

    # Nếu người dùng gửi form Đánh giá
    if request.method == 'POST' and request.user.is_authenticated:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        # Lưu vào Database
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "🎉 Cảm ơn ngài đã để lại đánh giá!")
        return redirect('product_detail', pk=pk) # Tải lại trang

    return render(request, 'core/product_detail.html', {'product': product, 'reviews': reviews})

# core/views.py
def map_view(request):
    stores = Store.objects.all()
    stores_data = []
    for store in stores:
        stores_data.append({
            'name': store.name,
            'address': store.address,
            'description': store.description or "Chưa có mô tả.",
            'hours': f"{store.opening_time.strftime('%H:%M')} - {store.closing_time.strftime('%H:%M')}" if store.opening_time else "Đang cập nhật",
            'rating': store.rating,
            'image': store.image_url or "https://via.placeholder.com/300x150", # Ảnh mặc định nếu thiếu
            'lat': store.location.y,
            'lng': store.location.x
        })
    stores_json = json.dumps(stores_data)
    return render(request, 'core/map.html', {'stores_json': stores_json})

# === 3. GIỎ HÀNG & THANH TOÁN ===
def cart_view(request):
    order, created = Order.objects.get_or_create(complete=False)
    items = order.orderitem_set.all()
    context = {'items': items, 'order': order}
    return render(request, 'core/cart.html', context)

def update_item(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    
    order, created = Order.objects.get_or_create(complete=False)
    product = Product.objects.get(id=productId)
    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
    
    if action == 'add':
        orderItem.quantity = (orderItem.quantity + 1)
        orderItem.save()
    elif action == 'remove':
        orderItem.quantity = (orderItem.quantity - 1)
        orderItem.save()
    
    if action == 'delete' or orderItem.quantity <= 0:
        orderItem.delete()
        
    return JsonResponse('Đã cập nhật giỏ hàng thành công!', safe=False)

def checkout_view(request):
    order, created = Order.objects.get_or_create(complete=False)
    items = order.orderitem_set.all()
    cart_total = sum([item.product.price * item.quantity for item in items])
    
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        
        order.complete = True
        order.save()
        messages.success(request, f"🎉 Đặt hàng thành công! Đơn hàng sẽ được giao đến {name} ({phone}).")
        return redirect('home')

    context = {'items': items, 'order': order, 'cart_total': cart_total}
    return render(request, 'core/checkout.html', context)

# === 4. XÁC THỰC NGƯỜI DÙNG ===
def register_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_user(request):
    logout(request)
    return redirect('login')

# === 5. CUSTOM ADMIN PANEL & THỐNG KÊ ===
@staff_member_required
def custom_admin_dashboard(request):
    products = Product.objects.all().order_by('-id')
    stores = Store.objects.all().order_by('-id')
    orders = Order.objects.filter(complete=True).order_by('-id')
    
    # --- THỜI GIAN HIỆN TẠI ---
    now = timezone.localtime(timezone.now())
    today = now.date()

    # 1. LOGIC BIỂU ĐỒ HÔM NAY (Theo từng giờ 0h -> 23h)
    today_labels = [f"{h}h" for h in range(24)]
    today_data = [0] * 24
    orders_today_list = Order.objects.filter(complete=True, date_ordered__date=today)
    for o in orders_today_list:
        hour = timezone.localtime(o.date_ordered).hour
        today_data[hour] += 1

    # 2. LOGIC BIỂU ĐỒ 7 NGÀY (Giữ nguyên logic của ngài)
    chart_labels = []
    chart_data = []
    weekday_names = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
    for i in range(6, -1, -1):
        check_date = today - timedelta(days=i)
        count = Order.objects.filter(complete=True, date_ordered__date=check_date).count()
        day_index = check_date.isoweekday() # 1=T2, 7=CN
        if day_index == 7: day_index = 0
        chart_labels.append(weekday_names[day_index])
        chart_data.append(count)

    # 3. HỆ THỐNG THỐNG KÊ (Stats)
    def get_stats(days):
        start_date = now - timedelta(days=days)
        if days == 1: # Nếu là hôm nay thì lọc chính xác từ 00:00 ngày hôm nay
            filtered_orders = Order.objects.filter(complete=True, date_ordered__date=today)
        else:
            filtered_orders = Order.objects.filter(complete=True, date_ordered__gte=start_date)
            
        order_count = filtered_orders.count()
        order_items = OrderItem.objects.filter(order__in=filtered_orders)
        revenue = order_items.aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0
        top_product = order_items.values('product__name').annotate(total_sold=Sum('quantity')).order_by('-total_sold').first()
        
        return {
            'order_count': order_count,
            'revenue': revenue,
            'top_name': top_product['product__name'] if top_product else 'Chưa có dữ liệu',
        }

    stats = {
        'day': get_stats(1),
        'week': get_stats(7),
    }

    context = {
        'products': products, 
        'stores': stores, 
        'orders': orders,
        'stats': stats,
        'today_labels': json.dumps(today_labels),
        'today_data': json.dumps(today_data),
        'chart_labels': json.dumps(chart_labels), 
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'core/admin_dashboard.html', context)


# ĐÂY LÀ HÀM XEM CHI TIẾT ĐƠN HÀNG ĐÃ ĐƯỢC PHỤC HỒI
@staff_member_required
def admin_order_detail(request, pk):
    order = get_object_or_404(Order, id=pk, complete=True)
    items = order.orderitem_set.all()
    total = sum([item.product.price * item.quantity for item in items])
    return render(request, 'core/admin_order_detail.html', {'order': order, 'items': items, 'total': total})

@staff_member_required
def admin_add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_admin_dashboard')
    else:
        form = ProductForm()
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Thêm Sản Phẩm Mới'})

@staff_member_required
def admin_edit_product(request, pk):
    # 1. Lấy sản phẩm cần sửa. Nếu không thấy hiện lỗi 404.
    product = get_object_or_404(Product, id=pk)

    if request.method == 'POST':
        # 2. Hứng dữ liệu từ các ô có thuộc tính 'name' trong HTML
        product.name = request.POST.get('name')
        
        # Xử lý giá tiền (loại bỏ dấu chấm/phẩy nếu ngài lỡ nhập 24.000.000)
        raw_price = request.POST.get('price', '0')
        product.price = float(raw_price.replace('.', '').replace(',', ''))
        
        # Hứng bộ sưu tập 5 ảnh chính
        product.image_url = request.POST.get('image_url')
        product.image_url_2 = request.POST.get('image_url_2')
        product.image_url_3 = request.POST.get('image_url_3')
        product.image_url_4 = request.POST.get('image_url_4')
        product.image_url_5 = request.POST.get('image_url_5')

        # Hứng mô tả và ảnh trong mô tả
        product.description = request.POST.get('description')
        product.desc_image_url = request.POST.get('desc_image_url')

        # 3. Lưu vào Database
        product.save()

        messages.success(request, f"🎉 Đã cập nhật siêu phẩm {product.name} thành công!")
        return redirect('custom_admin_dashboard')

    # 4. Khi vừa vào trang (GET): Gửi biến 'product' sang để hiện THÔNG TIN CŨ
    return render(request, 'core/admin_form.html', {'product': product})

@staff_member_required
def admin_delete_product(request, pk):
    product = get_object_or_404(Product, id=pk)
    product.delete()
    return redirect('custom_admin_dashboard')

@staff_member_required
def admin_add_store(request):
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_admin_dashboard')
    else:
        form = StoreForm()
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Thêm Cửa Hàng Mới'})

@staff_member_required
def admin_edit_store(request, pk):
    store = get_object_or_404(Store, id=pk)
    if request.method == 'POST':
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            return redirect('custom_admin_dashboard')
    else:
        form = StoreForm(instance=store)
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Sửa Thông Tin Cửa Hàng'})

@staff_member_required
def admin_delete_store(request, pk):
    store = get_object_or_404(Store, id=pk)
    store.delete()
    return redirect('custom_admin_dashboard')
# === API TÌM KIẾM TRỰC TIẾP (LIVE SEARCH) ===
def search_products(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        # Lấy tối đa 5 sản phẩm có tên chứa từ khóa (không phân biệt hoa/thường)
        products = Product.objects.filter(name__icontains=query)[:5]
        
        for p in products:
            results.append({
                'id': p.id,
                'name': p.name,
                'price': f"{p.price:,.0f}", # Định dạng lại giá tiền cho đẹp
                'image_url': p.image_url,
                'url': reverse('product_detail', args=[p.id]) # Tự động tạo link chi tiết
            })
       
    return JsonResponse({'data': results})