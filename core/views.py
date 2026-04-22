import json
import random
from datetime import timedelta
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ObjectDoesNotExist
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
    # 1. LẤY DỮ LIỆU TỪ REQUEST
    category_slug = request.GET.get('category') # Lấy slug danh mục (?category=ipad)
    query = request.GET.get('q') # Lấy từ khóa tìm kiếm (?q=iphone)
    
    # Mặc định lấy tất cả sản phẩm mới nhất
    all_products = Product.objects.all().order_by('-id')

    # 2. XỬ LÝ TÌM KIẾM (Nếu ngài có nhập vào ô Search)
    if query:
        all_products = all_products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        )

    # 3. XỬ LÝ LỌC DANH MỤC
    # Trẫm dùng category__slug vì thường Category là một Model riêng.
    # Nếu của ngài chỉ là một trường chữ (CharField), hãy đổi thành: category=category_slug
    if category_slug:
        all_products = all_products.filter(category__slug=category_slug)

    # --- LOGIC ĐIỀU KIỆN THIẾT BỊ ---
    is_mobile = request.user_agent.is_mobile
    
    # 4. PHÂN TRANG (Mobile hiện 4, Desktop hiện 8)
    per_page = 4 if is_mobile else 8 
    paginator = Paginator(all_products, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. TOP SELLING (Chỉ hiện ở trang đầu khi KHÔNG lọc và KHÔNG tìm kiếm)
    top_selling = []
    if not category_slug and not query and page_obj.number == 1:
        top_selling = Product.objects.all().order_by('-id')[:4]

    # 6. CHỌN GIAO DIỆN TƯƠNG ỨNG
    template_name = 'core/mobile_home.html' if is_mobile else 'core/home.html'

    context = {
        'products': page_obj,
        'top_selling': top_selling,
        'current_category': category_slug,
        'query': query, # Truyền ngược lại để ô tìm kiếm không bị mất chữ sau khi Search
        'is_mobile': is_mobile,
    }

    return render(request, template_name, context)

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
    # 1. LẤY DỮ LIỆU SẢN PHẨM & ĐÁNH GIÁ
    product = get_object_or_404(Product, id=pk)
    reviews = product.review_set.all().select_related('user').order_by('-created_at')

    # 2. KIỂM TRA TRẠNG THÁI ĐÁNH GIÁ CỦA NGƯỜI DÙNG
    has_reviewed = False
    if request.user.is_authenticated:
        # Kiểm tra xem User này đã tồn tại Review nào cho Product này chưa
        has_reviewed = Review.objects.filter(product=product, user=request.user).exists()

    # 3. XỬ LÝ GỬI ĐÁNH GIÁ (POST)
    if request.method == 'POST':
        if request.user.is_authenticated:
            # LỚP PHÒNG THỦ: Nếu đã đánh giá rồi thì không cho phép tạo thêm
            if has_reviewed:
                messages.warning(request, "Bẩm unicorn sama, ngài đã để lại dấu ấn tại đây rồi. Mỗi sản phẩm chỉ được đánh giá một lần để đảm bảo khách quan!")
                return redirect('product_detail', pk=pk)

            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            
            if rating and comment: # Kiểm tra dữ liệu đầu vào
                Review.objects.create(
                    product=product,
                    user=request.user,
                    rating=rating,
                    comment=comment
                )
                messages.success(request, "🎉 Cảm ơn unicorn sama đã để lại nhận xét!")
                return redirect('product_detail', pk=pk)
            else:
                messages.error(request, "Ngài vui lòng chọn số sao và nhập nội dung nhé!")
        else:
            messages.warning(request, "Đại vương cần đăng nhập để thực hiện đánh giá.")

    # 4. ĐIỀU KIỆN THIẾT BỊ & CHỌN TEMPLATE
    is_mobile = request.user_agent.is_mobile
    template_name = 'core/mobile_product_detail.html' if is_mobile else 'core/product_detail.html'

    context = {
        'product': product,
        'reviews': reviews,
        'is_mobile': is_mobile,
        'has_reviewed': has_reviewed, # TRUYỀN BIẾN NÀY SANG HTML ĐỂ ẨN FORM
    }

    return render(request, template_name, context)
# =========================
# 2. BẢN ĐỒ & CHI TIẾT KHO
# =========================

def map_view(request):
    stores = Store.objects.all()
    data = []
    
    for s in stores:
        if not s.location: 
            continue
        
        # Bốc tách tọa độ từ PostGIS POINT
        lng, lat = map(float, s.location.coords)
        
        # Bỏ qua nếu dữ liệu rác (4326)
        if lat == 4326 or lng == 4326: 
            continue

        data.append({
            'id': s.id,
            'name': s.name,
            'address': s.address,
            'lat': lat,
            'lng': lng,
            'image': s.image.url if s.image else 'https://via.placeholder.com/300x150?text=ONEWAY+Store',
            'is_open': s.is_open
        })
    context = {
        'stores': stores,     
        'stores_json': json.dumps(data), 
        'title': 'Hệ thống cửa hàng ONEWAY',
    }
    return render(request, 'core/map.html', context)

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
    
    # 🧹 THẦN CHÚ DIỆT MA: Xóa sạch các món hàng (OrderItem) mà sản phẩm gốc đã bị xóa (product=None)
    order.orderitem_set.filter(product__isnull=True).delete()
    
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
    
    # Thần chú diệt sản phẩm ma
    order.orderitem_set.filter(product__isnull=True).delete()
    
    if request.method == 'POST':
        order.complete = True
        # CHÌA KHÓA: Ép cập nhật giờ mua hàng đúng vào thời điểm bấm nút thanh toán
        order.date_ordered = timezone.now() 
        order.save()
        
        messages.success(request, "🎉 Đặt hàng thành công!")
        return redirect('home')
        
    items = order.orderitem_set.all()
    total = sum(i.product.price * i.quantity for i in items if i.product is not None)
    
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

    # 2. LOGIC PHÂN QUYỀN KHO (ĐÃ VÁ LỖI SẬP NGUỒN)
    # Nếu là Superuser: Thấy tất cả kho. Nếu là Quản lý: Chỉ thấy kho mình quản lý.
    if is_super:
        inventory_list = Inventory.objects.all().select_related('store', 'product')
        # Lấy danh sách nhân viên để phục vụ việc điều động (Chỉ Superuser thấy)
        staff_users = User.objects.filter(is_staff=True, is_superuser=False)
    else:
        # BỌC LỚP GIÁP BẢO VỆ: Nếu chưa có cửa hàng, trả về None thay vì báo lỗi đỏ trang
        try:
            managed_store = user.managed_store
        except ObjectDoesNotExist:
            managed_store = None

        if managed_store:
            inventory_list = Inventory.objects.filter(store=managed_store).select_related('product')
        else:
            inventory_list = Inventory.objects.none()
        staff_users = User.objects.none()

    # 3. TÌM KIẾM DỮ LIỆU
    q_prod = request.GET.get('search_product', '').strip()
    q_order = request.GET.get('search_order', '').strip()
    q_user = request.GET.get('search_user', '').strip()

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

    # 5. THỐNG KÊ STATS (Trẫm bổ sung lại phần ngài copy thiếu)
    def get_stats(days):
        start = now - timedelta(days=days)
        filt = Order.objects.filter(complete=True, date_ordered__date=today) if days==1 else Order.objects.filter(complete=True, date_ordered__gte=start)
        items = OrderItem.objects.filter(order__in=filt)
        rev = items.aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0
        top = items.values('product__name').annotate(sold=Sum('quantity')).order_by('-sold').first()
        return {'order_count': filt.count(), 'revenue': rev, 'top_name': top['product__name'] if top else 'N/A'}

    # 6. TỔNG HỢP CONTEXT VÀ TRẢ VỀ GIAO DIỆN
    context = {
        'products': products, 
        'stores': Store.objects.all(), 
        'orders': orders, 
        'users': users,
        'inventory_list': inventory_list, 
        'staff_users': staff_users,
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
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email này đã được sử dụng rồi, thưa đại vương!")
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
    if request.method == 'POST':
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, f"🎉 Mừng đại vương {request.user.username} giá lâm!")
            return redirect('home')
        else:
            messages.error(request, "❌ Sai tên đăng nhập hoặc mật khẩu. Vui lòng thử lại!")
            
    return render(request, 'core/login.html', {'form': form})

def logout_user(request):
    logout(request)
    return redirect('login')

def search_products(request):
    q = request.GET.get('q', '')
    res = []
    for p in Product.objects.filter(name__icontains=q)[:5]:
        res.append({'id': p.id, 'name': p.name, 'price': f"{p.price:,.0f}", 'image_url': p.image.url if p.image else '', 'url': reverse('product_detail', args=[p.id])})
    return JsonResponse({'data': res})

# core/views.py

def error_404_view(request, exception):
    # status=404 báo cho trình duyệt biết đây thực sự là lỗi, không phải trang bình thường
    return render(request, 'core/404.html', status=404)

def error_403_view(request, exception=None):
    return render(request, 'core/403.html', status=403)

def forgot_password_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        
        if user:
            # Tạo mã OTP thần sầu (6 chữ số)
            otp = str(random.randint(100000, 999999))
            
            # Lưu vào session. Chú ý: dùng dictionary lồng nhau
            request.session['reset_pwd_data'] = {
                'email': email, 
                'otp': otp, 
                'verified': False
            }
            # Ép Django lưu session ngay lập tức
            request.session.modified = True
            
            # Gửi chim bồ câu đưa tin
            subject = 'Khôi phục mật khẩu ONEWAY'
            message = f'Bẩm đại vương, mã OTP khôi phục mật khẩu của ngài là: {otp}'
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
            
            messages.info(request, f"Mã xác thực đã được gửi tới email {email}.")
            return redirect('verify_forgot_otp')
        else:
            messages.error(request, "Email này không tồn tại trong sổ sách vương quốc!")
            
    return render(request, 'core/forgot_password_otp.html')

def verify_forgot_otp(request):
    data = request.session.get('reset_pwd_data')
    
    if not data:
        messages.warning(request, "Lệnh truy cập bị từ chối. Vui lòng nhập email trước.")
        return redirect('forgot_password_otp')
        
    if request.method == 'POST':
        otp_input = request.POST.get('otp', '').strip()
        
        if otp_input == data['otp']:
            # CẬP NHẬT TRẠNG THÁI: Rất quan trọng để qua cửa ải tiếp theo
            data['verified'] = True
            request.session['reset_pwd_data'] = data
            request.session.modified = True 
            
            return redirect('set_new_password')
        else:
            messages.error(request, "Mã OTP không chính xác, thưa đại vương!")
            
    return render(request, 'core/verify_forgot_otp.html')

def set_new_password(request):
    data = request.session.get('reset_pwd_data')
    
    # 1. Kiểm tra quyền truy cập (thụt lề 4 dấu cách)
    if not data or not data.get('verified'):
        messages.error(request, "Ngài chưa vượt qua vòng kiểm tra OTP!")
        return redirect('forgot_password_otp')

    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')
        
        # 2. Kiểm tra mật khẩu (thụt lề 8 dấu cách)
        if not new_pass or len(new_pass) < 6:
            messages.error(request, "Mật khẩu quá ngắn, thưa đại vương!")
        elif new_pass == confirm_pass:
            # Lấy user và đổi mật khẩu (thụt lề 12 dấu cách)
            user = User.objects.filter(email=data['email']).first()
            if user:
                user.set_password(new_pass)
                user.save()
                request.session.pop('reset_pwd_data', None)
                messages.success(request, "Tái tạo mật khẩu thành công!")
                return redirect('login')
        else:
            # CÁI ELSE NÀY PHẢI THẲNG HÀNG VỚI IF (new_pass == confirm_pass)
            messages.error(request, "Mật khẩu nhập lại không khớp!")
            
    # 3. Luôn trả về template (thụt lề 4 dấu cách)
    return render(request, 'core/set_new_password.html')

def submit_review(request, product_id):
    if request.method == "POST":
        product = Product.objects.get(id=product_id)
        
        # Kiểm tra xem người dùng này đã đánh giá chưa
        already_reviewed = Review.objects.filter(user=request.user, product=product).exists()
        
        if already_reviewed:
            messages.warning(request, "Bẩm đại vương, người này đã đánh giá rồi, không thể thêm nữa!")
            return redirect('product_detail', pk=product_id)
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
        # 1. Tạm giữ lại, chưa lưu vội vào Database (commit=False)
        new_store = form.save(commit=False)
        
        # 2. Bắt lấy chuỗi tọa độ ẩn từ Form gửi lên
        location_data = request.POST.get('location')
        
        # 3. Ép kiểu tọa độ sang định dạng bản đồ GIS
        if location_data:
            try:
                from django.contrib.gis.geos import GEOSGeometry # Import phòng hờ nếu ngài chưa có
                new_store.location = GEOSGeometry(location_data)
            except (ValueError, TypeError):
                messages.error(request, "Tọa độ không hợp lệ, bản đồ từ chối nhận ghim!")
        
        # 4. Lưu chính thức mọi thứ (bao gồm cả tọa độ) vào Database
        new_store.save()
        messages.success(request, "📍 Đã khai trương chi nhánh mới và ghim lên bản đồ thành công!")
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
    # Chỉ tính tiền những item mà sản phẩm (product) vẫn còn tồn tại
    total = sum(i.product.price * i.quantity for i in items if i.product is not None)
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
def export_inventory_excel(request):
    # Lấy dữ liệu từ DB (chỉ lấy các cột cần thiết)
    products = Product.objects.all().values('id', 'name', 'category', 'price', 'stock')
    
    # Chuyển đổi thành DataFrame của Pandas
    df = pd.DataFrame(products)
    
    # Đổi tên cột tiếng Anh sang tiếng Việt cho đẹp file Excel
    df.rename(columns={
        'id': 'Mã SP', 
        'name': 'Tên sản phẩm', 
        'category': 'Mã danh mục', 
        'price': 'Giá bán', 
        'stock': 'Tồn kho hiện tại'
    }, inplace=True)
    
    # Cấu hình file trả về cho trình duyệt
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="XuatKho_ONEWAY.xlsx"'
    
    # Ghi dữ liệu ra file Excel
    df.to_excel(response, index=False, engine='openpyxl')
    return response


# --- 2. TÍNH NĂNG NHẬP KHO (Đọc file Excel để cộng số lượng) ---
def import_inventory_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
            count_success = 0
            
            # Lấy chi nhánh mặc định nếu người dùng là Quản lý chi nhánh
            default_store = getattr(request.user, 'managed_store', None) if not request.user.is_superuser else None

            for index, row in df.iterrows():
                product_id = row.get('Mã SP')
                quantity_added = row.get('Số lượng nhập') # Tên cột khớp với file Excel của ngài
                
                if pd.notna(product_id) and pd.notna(quantity_added):
                    try:
                        product = Product.objects.get(id=int(product_id))
                        
                        # XÁC ĐỊNH CHI NHÁNH ĐỂ NHẬP KHO
                        if request.user.is_superuser:
                            # Nếu là sếp tổng, bắt buộc file Excel phải có cột "Mã Chi Nhánh"
                            store_id_excel = row.get('Mã Chi Nhánh')
                            if pd.isna(store_id_excel):
                                continue # Bỏ qua nếu thiếu mã chi nhánh
                            store = Store.objects.get(id=int(store_id_excel))
                        else:
                            # Nếu là Quản lý, tự động nhét hàng vào chi nhánh của họ
                            store = default_store
                            if not store:
                                continue 
                                
                        # TÌM HOẶC TẠO KHO & CỘNG DỒN SỐ LƯỢNG
                        inventory, created = Inventory.objects.get_or_create(store=store, product=product)
                        
                        # Đảm bảo số lượng ban đầu không bị None
                        if inventory.quantity is None:
                            inventory.quantity = 0
                            
                        # Cộng dồn số lượng nhập vào kho
                        inventory.quantity += int(quantity_added)
                        inventory.save()
                        
                        count_success += 1
                        
                    except (Product.DoesNotExist, Store.DoesNotExist):
                        continue # Bỏ qua nếu gõ sai Mã SP hoặc Mã Chi Nhánh trong file
                        
            if count_success > 0:
                messages.success(request, f"🎉 Đã nhập kho thành công {count_success} dòng dữ liệu!")
            else:
                messages.error(request, "❌ Không nhập được sản phẩm nào. Vui lòng kiểm tra lại Mã SP và Tên cột.")
            
        except Exception as e:
            messages.error(request, f"❌ Lỗi đọc file: {str(e)}")
            
    return redirect(request.META.get('HTTP_REFERER', '/quan-tri/'))