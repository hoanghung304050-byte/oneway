from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F
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
    products = Product.objects.all()[:4]
    return render(request, 'core/home.html', {'products': products})

# === 2. SẢN PHẨM & BẢN ĐỒ ===
def product_list(request):
    products = Product.objects.all()
    return render(request, 'core/product_list.html', {'products': products})

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

def map_view(request):
    stores = Store.objects.all()
    stores_data = []
    for store in stores:
        stores_data.append({
            'name': store.name,
            'address': store.address,
            'phone': store.phone,
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
    
    # HỆ THỐNG PHÂN TÍCH DỮ LIỆU (ANALYTICS)
    def get_stats(days):
        start_date = timezone.now() - timedelta(days=days)
        filtered_orders = Order.objects.filter(complete=True, date_ordered__gte=start_date)
        order_count = filtered_orders.count()
        order_items = OrderItem.objects.filter(order__in=filtered_orders)
        revenue = order_items.aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0
        top_product = order_items.values('product__name').annotate(total_sold=Sum('quantity')).order_by('-total_sold').first()
        
        return {
            'order_count': order_count,
            'revenue': revenue,
            'top_name': top_product['product__name'] if top_product else 'Chưa có dữ liệu',
            'top_qty': top_product['total_sold'] if top_product else 0
        }

    stats = {
        'day': get_stats(1),
        'week': get_stats(7),
        'month': get_stats(30),
        'year': get_stats(365),
    }

    return render(request, 'core/admin_dashboard.html', {
        'products': products, 
        'stores': stores, 
        'orders': orders,
        'stats': stats
    })

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
    product = get_object_or_404(Product, id=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('custom_admin_dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Sửa Sản Phẩm'})

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