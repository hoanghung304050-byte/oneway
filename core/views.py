import json
import random
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.gis.geos import GEOSGeometry
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.core.paginator import Paginator

from .models import Order, OrderItem, Product, Store, Review, Inventory
from .forms import ProductForm, StoreForm

# =========================
# 1. TRANG CHỦ & DANH SÁCH
# =========================
# === THÊM LẠI CÁC TRANG CƠ BẢN BỊ THIẾU ===
def about(request):
    return render(request, 'core/about.html')

def warranty(request):
    return render(request, 'core/warranty.html')

def contact(request):
    return render(request, 'core/contact.html')
def home_view(request):
    category_slug = request.GET.get('category')
    all_products = Product.objects.all().order_by('-id')

    if category_slug:
        all_products = all_products.filter(category=category_slug)

    paginator = Paginator(all_products, 8)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Top selling chỉ hiện ở trang đầu khi không lọc
    top_selling = Product.objects.all().order_by('-id')[:4] if not category_slug and page_obj.number == 1 else []

    return render(request, 'core/home.html', {
        'products': page_obj,
        'top_selling': top_selling,
        'current_category': category_slug,
    })

def product_list(request):
    category_slug = request.GET.get('category')
    selected_brands = request.GET.getlist('brands')
    products = Product.objects.all().order_by('-id')

    if category_slug:
        products = products.filter(category=category_slug)

    if selected_brands:
        brand_query = Q()
        for b in selected_brands:
            brand_query |= Q(brand__iexact=b)
        products = products.filter(brand_query)

    available_brands = Product.objects.filter(category=category_slug).values_list('brand', flat=True).distinct()

    return render(request, 'core/product_list.html', {
        'products': products,
        'current_category': category_slug,
        'selected_brands': selected_brands,
        'available_brands': available_brands,
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, id=pk)
    reviews = product.review_set.all().order_by('-created_at')

    if request.method == 'POST' and request.user.is_authenticated:
        Review.objects.create(
            product=product,
            user=request.user,
            rating=request.POST.get('rating'),
            comment=request.POST.get('comment')
        )
        messages.success(request, "🎉 Cảm ơn ngài đã đánh giá!")
        return redirect('product_detail', pk=pk)

    return render(request, 'core/product_detail.html', {'product': product, 'reviews': reviews})

# =========================
# 2. BẢN ĐỒ & CHI TIẾT KHO
# =========================

def map_view(request):
    stores = Store.objects.all()
    data = []
    for s in stores:
        if not s.location: continue
        lng, lat = map(float, s.location.coords)
        if lat == 4326 or lng == 4326: continue

        data.append({
            'id': s.id,
            'name': s.name,
            'address': s.address,
            'lat': lat,
            'lng': lng,
            'image': s.image.url if s.image else 'https://via.placeholder.com/300x150?text=ONEWAY+Store',
            'is_open': s.is_open
        })
    return render(request, 'core/map.html', {'stores_json': json.dumps(data)})

def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    # Chỉ lấy những sản phẩm còn hàng (quantity > 0)
    inventory_items = Inventory.objects.filter(store=store, quantity__gt=0).select_related('product')
    
    return render(request, 'core/store_detail.html', {
        'store': store,
        'inventory_items': inventory_items
    })
@staff_member_required
def admin_edit_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            obj = form.save(commit=False)
            location_data = request.POST.get('location')
            
            if location_data:
                try:
                    # Ép kiểu thủ công để đảm bảo GDAL không nổi giận
                    obj.location = GEOSGeometry(location_data)
                except (ValueError, TypeError):
                    messages.error(request, "Tọa độ không hợp lệ!")
            
            obj.save()
            return redirect('custom_admin_dashboard')
    else:
        form = StoreForm(instance=store)
    
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Sửa Cửa Hàng'})
@staff_member_required
def update_stock(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 0))
        
        # Nếu là Superuser thì phải chọn Store, nếu là Manager thì lấy store của họ
        if request.user.is_superuser:
            store_id = request.POST.get('store_id')
            store = get_object_or_404(Store, id=store_id)
        else:
            store = getattr(request.user, 'managed_store', None)
            if not store:
                messages.error(request, "Ngài chưa được phân quản lý chi nhánh nào!")
                return redirect('custom_admin_dashboard')

        product = get_object_or_404(Product, id=product_id)
        
        # Cập nhật hoặc tạo mới tồn kho
        inventory, created = Inventory.objects.get_or_create(store=store, product=product)
        inventory.quantity = quantity # Hoặc inventory.quantity += quantity nếu muốn cộng dồn
        inventory.save()

        messages.success(request, f"📦 Đã cập nhật kho: {product.name} tại {store.name} - SL: {quantity}")
    
    return redirect('custom_admin_dashboard')

# =========================
# 3. GIỎ HÀNG & THANH TOÁN
# =========================

def cart_view(request):
    order, _ = Order.objects.get_or_create(complete=False)
    return render(request, 'core/cart.html', {'order': order, 'items': order.orderitem_set.all()})

def update_item(request):
    data = json.loads(request.body)
    product = Product.objects.get(id=data['productId'])
    order, _ = Order.objects.get_or_create(complete=False)
    item, _ = OrderItem.objects.get_or_create(order=order, product=product)
    if data['action'] == 'add': item.quantity += 1
    elif data['action'] == 'remove': item.quantity -= 1
    if item.quantity <= 0 or data['action'] == 'delete': item.delete()
    else: item.save()
    return JsonResponse('Updated', safe=False)

def checkout_view(request):
    order, _ = Order.objects.get_or_create(complete=False)
    if request.method == 'POST':
        order.complete = True; order.save()
        messages.success(request, "🎉 Đặt hàng thành công!")
        return redirect('home')
    items = order.orderitem_set.all()
    total = sum(i.product.price * i.quantity for i in items)
    return render(request, 'core/checkout.html', {'order': order, 'items': items, 'cart_total': total})

# =========================
# 4. QUẢN TRỊ (ADMIN DASHBOARD)
# =========================

@staff_member_required
def custom_admin_dashboard(request):
    # 1. PHÂN QUYỀN CƠ BẢN
    user = request.user
    is_super = user.is_superuser
    is_staff_only = user.groups.filter(name='NhanVien').exists()
    is_manager = is_super or (user.is_staff and not is_staff_only)

    # 2. LOGIC PHÂN QUYỀN KHO (MỚI)
    # Nếu là Superuser: Thấy tất cả kho. Nếu là Quản lý: Chỉ thấy kho mình quản lý.
    if is_super:
        inventory_list = Inventory.objects.all().select_related('store', 'product')
        # Lấy danh sách nhân viên để phục vụ việc điều động (Chỉ Superuser thấy)
        staff_users = User.objects.filter(is_staff=True, is_superuser=False)
    else:
        # Tìm chi nhánh mà User này đang quản lý (Dựa trên field manager trong model Store)
        managed_store = getattr(user, 'managed_store', None)
        if managed_store:
            inventory_list = Inventory.objects.filter(store=managed_store).select_related('product')
        else:
            inventory_list = Inventory.objects.none()
        staff_users = User.objects.none()

    # 3. TÌM KIẾM DỮ LIỆU
    q_prod = request.GET.get('search_product', '')
    q_order = request.GET.get('search_order', '')
    q_user = request.GET.get('search_user', '')

    now = timezone.localtime(timezone.now())
    today = now.date()

    # Query sản phẩm & đơn hàng
    products = Product.objects.all().order_by('-id')
    if q_prod: products = products.filter(Q(name__icontains=q_prod) | Q(id__icontains=q_prod))

    orders = Order.objects.filter(complete=True).order_by('-id')
    if not is_manager: orders = orders.filter(date_ordered__date=today)
    if q_order: orders = orders.filter(id__icontains=q_order)

    # Chỉ manager/super mới thấy danh sách người dùng
    users = User.objects.all().order_by('-date_joined') if is_manager else User.objects.none()
    if q_user and is_manager: 
        users = users.filter(Q(username__icontains=q_user) | Q(email__icontains=q_user))

    # 4. LOGIC BIỂU ĐỒ (Giữ nguyên của ngài)
    today_labels = [f"{h}h" for h in range(24)]
    today_data = [0] * 24
    for o in Order.objects.filter(complete=True, date_ordered__date=today):
        today_data[timezone.localtime(o.date_ordered).hour] += 1

    chart_labels, chart_data = [], []
    weekday_names = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(weekday_names[d.isoweekday() % 7])
        chart_data.append(Order.objects.filter(complete=True, date_ordered__date=d).count())

    # 5. THỐNG KÊ STATS (Giữ nguyên của ngài)
    def get_stats(days):
        start = now - timedelta(days=days)
        filt = Order.objects.filter(complete=True, date_ordered__date=today) if days==1 else Order.objects.filter(complete=True, date_ordered__gte=start)
        items = OrderItem.objects.filter(order__in=filt)
        rev = items.aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0
        top = items.values('product__name').annotate(sold=Sum('quantity')).order_by('-sold').first()
        return {'order_count': filt.count(), 'revenue': rev, 'top_name': top['product__name'] if top else 'N/A'}

    # 6. TỔNG HỢP CONTEXT
    context = {
        'products': products, 
        'stores': Store.objects.all(), # Luôn lấy list store để hiển thị hoặc điều động
        'orders': orders, 
        'users': users,
        'inventory_list': inventory_list, # Truyền danh sách kho đã lọc
        'staff_users': staff_users,       # Truyền danh sách nhân viên (cho Superuser)
        'stats': {'day': get_stats(1), 'week': get_stats(7)},
        'is_manager': is_manager, 
        'is_super': is_super,
        'today_labels': json.dumps(today_labels), 
        'today_data': json.dumps(today_data),
        'chart_labels': json.dumps(chart_labels), 
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'core/admin_dashboard.html', context)

# =========================
# 5. XÁC THỰC & KHÁC
# =========================

def register(request):
    if request.method == 'POST':
        username, email, password = request.POST.get('username'), request.POST.get('email'), request.POST.get('password')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Tên đã tồn tại!")
            return render(request, 'core/register.html')
        
        otp = str(random.randint(100000, 999999))
        request.session['reg_data'] = {'username': username, 'email': email, 'password': password, 'otp': otp}
        send_mail('OTP ONEWAY', f'Mã: {otp}', settings.EMAIL_HOST_USER, [email])
        return redirect('verify_email')
    return render(request, 'core/register.html')

def verify_email(request):
    data = request.session.get('reg_data')
    if request.method == 'POST' and data and request.POST.get('otp') == data['otp']:
        User.objects.create_user(username=data['username'], email=data['email'], password=data['password'])
        del request.session['reg_data']
        return redirect('login')
    return render(request, 'core/verify_email.html')

def login_page(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('home')
    return render(request, 'core/login.html', {'form': form})

def logout_user(request):
    logout(request); return redirect('login')

def search_products(request):
    q = request.GET.get('q', '')
    res = []
    for p in Product.objects.filter(name__icontains=q)[:5]:
        res.append({'id': p.id, 'name': p.name, 'price': f"{p.price:,.0f}", 'image_url': p.image.url if p.image else '', 'url': reverse('product_detail', args=[p.id])})
    return JsonResponse({'data': res})
# =========================
# 6. QUẢN TRỊ SẢN PHẨM
# =========================

@staff_member_required
def admin_add_product(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "🎉 Đã nhập kho siêu phẩm mới!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Thêm Sản Phẩm'})

@staff_member_required
def admin_edit_product(request, pk):
    product = get_object_or_404(Product, id=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"🎉 Đã cập nhật {product.name}!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Sửa Sản Phẩm'})

@staff_member_required
def admin_delete_product(request, pk):
    # Chỉ Quản lý mới được xóa, nhân viên chỉ được xem/sửa
    if request.user.groups.filter(name='NhanVien').exists():
        messages.error(request, "Ngài không đủ quyền hạn để thực hiện lệnh trảm sản phẩm!")
    else:
        product = get_object_or_404(Product, id=pk)
        product.delete()
        messages.success(request, "💥 Đã xóa sản phẩm khỏi hệ thống!")
    return redirect('custom_admin_dashboard')

# =========================
# 7. QUẢN TRỊ CỬA HÀNG
# =========================

@staff_member_required
def admin_add_store(request):
    form = StoreForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "📍 Đã khai trương chi nhánh mới!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Thêm Cửa Hàng'})

@staff_member_required
def admin_edit_store(request, pk):
    store = get_object_or_404(Store, id=pk)
    form = StoreForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"📍 Đã cập nhật chi nhánh {store.name}!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Sửa Cửa Hàng'})

@staff_member_required
def admin_delete_store(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Chỉ đại vương mới có quyền đóng cửa chi nhánh!")
    else:
        store = get_object_or_404(Store, id=pk)
        store.delete()
        messages.success(request, "💥 Chi nhánh đã được giải tỏa!")
    return redirect('custom_admin_dashboard')

# =========================
# 8. CHI TIẾT ĐƠN HÀNG & PHÂN QUYỀN
# =========================
@staff_member_required
def toggle_user_staff(request, user_id):
    """Bật/Tắt quyền truy cập Admin cho người dùng"""
    if request.user.is_superuser:
        target_user = get_object_or_404(User, id=user_id)
        
        # Ngăn chặn tác động vào chính mình hoặc các Superuser khác
        if target_user != request.user and not target_user.is_superuser:
            target_user.is_staff = not target_user.is_staff
            target_user.save()
            status = "Admin/Nhân viên" if target_user.is_staff else "Khách hàng"
            messages.success(request, f"🎉 Đã chuyển {target_user.username} thành {status}!")
        else:
            messages.error(request, "Ngài không thể tác động vào tài khoản cấp cao này!")
    else:
        messages.error(request, "Chỉ Superuser mới có quyền ban phát chức vị!")
        
    return redirect('custom_admin_dashboard')


@staff_member_required
def delete_user(request, user_id):
    """Xóa vĩnh viễn tài khoản người dùng"""
    if request.user.is_superuser:
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user == request.user:
            messages.error(request, "Ngài không thể tự xóa chính mình! Vương quốc vẫn cần ngài điều hành.")
        elif target_user.is_superuser:
            messages.error(request, "Không thể trảm một Superuser khác!")
        else:
            name = target_user.username
            target_user.delete()
            messages.success(request, f"💥 Đã xóa vĩnh viễn tài khoản: {name}")
    else:
        messages.error(request, "Ngài không đủ quyền hạn để thực hiện lệnh trảm này!")
        
    return redirect('custom_admin_dashboard')

@staff_member_required
def admin_order_detail(request, pk):
    order = get_object_or_404(Order, id=pk, complete=True)
    items = order.orderitem_set.all()
    # Tính tổng tiền bao gồm cả phí ship (nếu có trường shipping_fee)
    total = sum(i.product.price * i.quantity for i in items)
    return render(request, 'core/admin_order_detail.html', {
        'order': order, 
        'items': items, 
        'total': total
    })

@staff_member_required
def change_user_role(request, user_id, role):
    if not request.user.is_superuser:
        return redirect('custom_admin_dashboard')
    
    target_user = get_object_or_404(User, id=user_id)
    if target_user.is_superuser: return redirect('custom_admin_dashboard')

    nv_group, _ = Group.objects.get_or_create(name='NhanVien')
    
    if role == 'khach':
        target_user.is_staff = False
        target_user.groups.remove(nv_group)
    elif role == 'nhanvien':
        target_user.is_staff = True
        target_user.groups.add(nv_group)
    elif role == 'quanly':
        target_user.is_staff = True
        target_user.groups.remove(nv_group)

    target_user.save()
    messages.success(request, f"Đã sắc phong {target_user.username} thành {role.upper()}!")
    return redirect('custom_admin_dashboard')
@staff_member_required
def transfer_manager(request):
    if not request.user.is_superuser:
        messages.error(request, "Chỉ Đại vương mới có quyền điều phối nhân sự!")
        return redirect('custom_admin_dashboard')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_store_id = request.POST.get('store_id')
        
        user_to_move = get_object_or_404(User, id=user_id)
        new_store = get_object_or_404(Store, id=new_store_id)

        # BƯỚC THIẾT QUÂN LUẬT: 
        # 1. Xóa quản lý cũ tại Store mới (nếu có) để tránh xung đột OneToOne
        Store.objects.filter(manager=user_to_move).update(manager=None)
        
        # 2. Gán người này vào Store mới
        new_store.manager = user_to_move
        new_store.save()

        messages.success(request, f"🚀 Đã điều động {user_to_move.username} về làm Quản lý tại {new_store.name}")
    
    return redirect('custom_admin_dashboard')