import json, random, os
from datetime import timedelta
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from functools import wraps
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage, FileSystemStorage

from .models import Order, OrderItem, Product, Store, Review, Inventory, CompanyInfo, CompanyImage, StoreImage
from .forms import ProductForm, StoreForm

def custom_staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login') 
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied 
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# =========================
# 1. TRANG CHỦ & DANH SÁCH
# =========================
def about(request):
    info = CompanyInfo.objects.first()
    if info:
        banners = info.images.filter(is_banner=True)
        stories = info.images.filter(is_banner=False)
    else:
        banners = stories = []

    return render(request, 'core/about.html', {
        'about': info,
        'banners': banners,
        'stories': stories
    })

def warranty(request):
    return render(request, 'core/warranty.html')

def contact(request):
    return render(request, 'core/contact.html')
def home_view(request):
    # 1. LẤY DỮ LIỆU TỪ REQUEST
    category_slug = request.GET.get('category') 
    query = request.GET.get('q') 
    
    all_products = Product.objects.all().order_by('-id')

    # 2. XỬ LÝ TÌM KIẾM 
    if query:
        all_products = all_products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        )

    # 3. XỬ LÝ LỌC DANH MỤC
    if category_slug:
        all_products = all_products.filter(category__slug=category_slug)

    is_mobile = request.user_agent.is_mobile
    
    # 4. PHÂN TRANG 
    per_page = 4 if is_mobile else 8 
    paginator = Paginator(all_products, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. TOP SELLING 
    top_selling = []
    if not category_slug and not query and page_obj.number == 1:
        top_selling = Product.objects.all().order_by('-id')[:4]

    # 6. CHỌN GIAO DIỆN TƯƠNG ỨNG
    template_name = 'core/mobile_home.html' if is_mobile else 'core/home.html'

    context = {
        'products': page_obj,
        'top_selling': top_selling,
        'current_category': category_slug,
        'query': query, 
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
        has_reviewed = Review.objects.filter(product=product, user=request.user).exists()

    # 3. XỬ LÝ GỬI ĐÁNH GIÁ (POST)
    if request.method == 'POST':
        if request.user.is_authenticated:
            if has_reviewed:
                messages.warning(request, "bạn đã đánh giá sản phẩm này rồi")
                return redirect('product_detail', pk=pk)

            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            
            if rating and comment:
                Review.objects.create(
                    product=product,
                    user=request.user,
                    rating=rating,
                    comment=comment
                )
                messages.success(request, "Cảm ơn bạn đã để lại nhận xét!")
                return redirect('product_detail', pk=pk)
            else:
                messages.error(request, "vui lòng chọn số sao và nhập nội dung nhé!")
        else:
            messages.warning(request, "Bạn cần đăng nhập để thực hiện đánh giá.")

    # 4. ĐIỀU KIỆN THIẾT BỊ & CHỌN TEMPLATE
    is_mobile = request.user_agent.is_mobile
    template_name = 'core/mobile_product_detail.html' if is_mobile else 'core/product_detail.html'

    context = {
        'product': product,
        'reviews': reviews,
        'is_mobile': is_mobile,
        'has_reviewed': has_reviewed,
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
        
        lng, lat = map(float, s.location.coords)
        
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
    inventory_items = Inventory.objects.filter(store=store, quantity__gt=0).select_related('product')
    
    return render(request, 'core/store_detail.html', {
        'store': store,
        'inventory_items': inventory_items
    })
@custom_staff_required
def admin_edit_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            obj = form.save(commit=False)
            location_data = request.POST.get('location')
            
            if location_data:
                try:
                    obj.location = GEOSGeometry(location_data)
                except (ValueError, TypeError):
                    messages.error(request, "Tọa độ không hợp lệ!")
            
            # 1. Lưu thông tin chính của Store
            obj.save() 

            # 2. Xử lý ảnh Banner (Phải nằm trong if form.is_valid)
            banners = request.FILES.getlist('banners')
            if banners:
                print(f"DEBUG: Đang xử lý {len(banners)} ảnh banner cho Store {obj.id}")
                
                # Xóa sạch ảnh cũ để chống cộng dồn
                obj.gallery.all().delete() 
                
                # Lưu toàn bộ bộ ảnh mới
                for img in banners:
                    StoreImage.objects.create(store=obj, image=img)
                
                print("DEBUG: Đã cập nhật xong bộ banner mới.")
            
            # 3. CHUYỂN HƯỚNG (Nằm ngoài vòng lặp for, nhưng trong if form.is_valid)
            return redirect('custom_admin_dashboard')
            
    else:
        form = StoreForm(instance=store)
    
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Sửa Cửa Hàng'})
@custom_staff_required
def update_stock(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 0))
        
        if request.user.is_superuser:
            store_id = request.POST.get('store_id')
            store = get_object_or_404(Store, id=store_id)
        else:
            store = getattr(request.user, 'managed_store', None)
            if not store:
                messages.error(request, "bạn chưa được phân quản lý chi nhánh nào!")
                return redirect('custom_admin_dashboard')

        product = get_object_or_404(Product, id=product_id)
        
        inventory, created = Inventory.objects.get_or_create(store=store, product=product)
        inventory.quantity = quantity 
        inventory.save()

        messages.success(request, f" Đã cập nhật kho: {product.name} tại {store.name} - SL: {quantity}")
    
    return redirect('custom_admin_dashboard')

# =========================
# 3. GIỎ HÀNG & THANH TOÁN
# =========================

def cart_view(request):
    order, _ = Order.objects.get_or_create(complete=False)
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
    order.orderitem_set.filter(product__isnull=True).delete()
    
    if request.method == 'POST':
        order.complete = True
        order.date_ordered = timezone.now() 
        order.save()
        
        messages.success(request, " Đặt hàng thành công!")
        return redirect('home')
        
    items = order.orderitem_set.all()
    total = sum(i.product.price * i.quantity for i in items if i.product is not None)
    
    return render(request, 'core/checkout.html', {'order': order, 'items': items, 'cart_total': total})

# =========================
# 4. QUẢN TRỊ (ADMIN DASHBOARD)
# =========================
@custom_staff_required
def custom_admin_dashboard(request):
    # 1. PHÂN QUYỀN CƠ BẢN
    user = request.user
    is_super = user.is_superuser
    is_staff_only = user.groups.filter(name='NhanVien').exists()
    is_manager = is_super or (user.is_staff and not is_staff_only)

    # 2. LOGIC PHÂN QUYỀN KHO 
    # Nếu là Superuser: Thấy tất cả kho. Nếu là Quản lý: Chỉ thấy kho mình quản lý.
    if is_super:
        inventory_list = Inventory.objects.all().select_related('store', 'product')
        # Lấy danh sách nhân viên để phục vụ việc điều động (Chỉ Superuser thấy)
        staff_users = User.objects.filter(is_staff=True, is_superuser=False)
    else:
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

    # 4. LOGIC BIỂU ĐỒ 
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

    # 5. THỐNG KÊ STATS 
    def get_stats(days):
        start = now - timedelta(days=days)
        filt = Order.objects.filter(complete=True, date_ordered__date=today) if days==1 else Order.objects.filter(complete=True, date_ordered__gte=start)
        items = OrderItem.objects.filter(order__in=filt)
        rev = items.aggregate(total=Sum(F('quantity') * F('product__price')))['total'] or 0
        top = items.values('product__name').annotate(sold=Sum('quantity')).order_by('-sold').first()
        return {'order_count': filt.count(), 'revenue': rev, 'top_name': top['product__name'] if top else 'N/A'}
    
    about_data = CompanyInfo.objects.first()
    if not about_data:
        about_data = CompanyInfo.objects.create(title="Giới thiệu Oneway Store")
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
        'about': about_data,
    }
    return render(request, 'core/admin_dashboard.html', context)

from django.contrib import messages

@custom_staff_required
def manage_about(request):
    if request.method == 'POST':
# 1. Lấy ra bản ghi MỚI NHẤT
        info = CompanyInfo.objects.last()
        
        # 2. Nếu chưa có thì tạo mới
        if not info:
            info = CompanyInfo.objects.create(title="Giới thiệu Oneway Store")
        else:
            # 3. XOÁ TẤT CẢ các bản ghi khác để tránh loạn dữ liệu
            CompanyInfo.objects.exclude(id=info.id).delete()
        info.title = request.POST.get('title', '')
        info.description = request.POST.get('description', '')
        info.save()

        # Xử lý Upload Banner 
        banner_files = request.FILES.getlist('banners')
        if banner_files:
            CompanyImage.objects.filter(info=info, is_banner=True).delete()
            for f in banner_files:
                CompanyImage.objects.create(info=info, image=f, is_banner=True)

        # Xử lý Upload Story
        story_files = request.FILES.getlist('stories')
        if story_files:
            CompanyImage.objects.filter(info=info, is_banner=False).delete()
            for f in story_files:
                CompanyImage.objects.create(info=info, image=f, is_banner=False)
        
        messages.success(request, "trang giới thiệu đã được làm mới!")
    return redirect(request.META.get('HTTP_REFERER', '/quan-tri/'))

def about_view(request):
    info = CompanyInfo.objects.first()
    
    if info:
        banners = info.images.filter(is_banner=True)
        stories = info.images.filter(is_banner=False)
    else:
        banners = stories = []

    return render(request, 'core/about.html', {
        'about': info,
        'banners': banners,
        'stories': stories
    })

@csrf_exempt
@custom_staff_required
def upload_editor_image(request):
    try:
        if request.method == 'POST' and request.FILES.get('upload'):
            upload = request.FILES['upload']
            
            # 1. Tự động tạo thư mục nếu chưa có
            save_path = os.path.join(settings.MEDIA_ROOT, 'editor_images')
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            
            # 2. Lưu ảnh cực kỳ an toàn
            fs = FileSystemStorage(location=save_path, base_url=settings.MEDIA_URL + 'editor_images/')
            filename = fs.save(upload.name, upload)
            file_url = fs.url(filename)
            
            # 3. Trả về đúng chuẩn để ảnh mờ nét trở lại
            return JsonResponse({
                'uploaded': 1,
                'fileName': filename,
                'url': file_url
            })
            
    except Exception as e:
        return JsonResponse({'uploaded': 0, 'error': {'message': f'Lỗi hệ thống: {str(e)}'}})
        
    return JsonResponse({'uploaded': 0, 'error': {'message': 'Không nhận được ảnh!'}})
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
            messages.error(request, "Email này đã được sử dụng rồi!")
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
            messages.success(request, f" Xin chào {request.user.username} !")
            return redirect('home')
        else:
            messages.error(request, " Sai tên đăng nhập hoặc mật khẩu. Vui lòng thử lại!")
            
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
    return render(request, 'core/404.html', status=404)
    

def error_403_view(request, exception=None):
    return render(request, 'core/403.html', status=403)

def forgot_password_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        
        if user:
            otp = str(random.randint(100000, 999999))
            
            request.session['reset_pwd_data'] = {
                'email': email, 
                'otp': otp, 
                'verified': False
            }
            request.session.modified = True
            

            subject = 'Khôi phục mật khẩu ONEWAY'
            message = f' mã OTP khôi phục mật khẩu của bạn là: {otp}'
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
            
            messages.info(request, f"Mã xác thực đã được gửi tới email {email}.")
            return redirect('verify_forgot_otp')
        else:
            messages.error(request, "Email này không tồn tại ")
            
    return render(request, 'core/forgot_password_otp.html')

def verify_forgot_otp(request):
    data = request.session.get('reset_pwd_data')
    
    if not data:
        messages.warning(request, "Lệnh truy cập bị từ chối. Vui lòng nhập email trước.")
        return redirect('forgot_password_otp')
        
    if request.method == 'POST':
        otp_input = request.POST.get('otp', '').strip()
        
        if otp_input == data['otp']:
            # CẬP NHẬT TRẠNG THÁI
            data['verified'] = True
            request.session['reset_pwd_data'] = data
            request.session.modified = True 
            
            return redirect('set_new_password')
        else:
            messages.error(request, "Mã OTP không chính xác")
            
    return render(request, 'core/verify_forgot_otp.html')

def set_new_password(request):
    data = request.session.get('reset_pwd_data')
    
    # 1. Kiểm tra quyền truy cập 
    if not data or not data.get('verified'):
        messages.error(request, "bạn chưa kiểm tra OTP!")
        return redirect('forgot_password_otp')

    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')
        
        if not new_pass or len(new_pass) < 6:
            messages.error(request, "Mật khẩu quá ngắn")
        elif new_pass == confirm_pass:
            user = User.objects.filter(email=data['email']).first()
            if user:
                user.set_password(new_pass)
                user.save()
                request.session.pop('reset_pwd_data', None)
                messages.success(request, "khôi phục mật khẩu thành công!")
                return redirect('login')
        else:
            messages.error(request, "Mật khẩu nhập lại không khớp!")
    return render(request, 'core/set_new_password.html')

def submit_review(request, product_id):
    if request.method == "POST":
        product = Product.objects.get(id=product_id)
        already_reviewed = Review.objects.filter(user=request.user, product=product).exists()
        
        if already_reviewed:
            messages.warning(request, " Bạn đã đánh giá rồi, không thể thêm nữa!")
            return redirect('product_detail', pk=product_id)
# =========================
# 6. QUẢN TRỊ SẢN PHẨM
# =========================

@custom_staff_required  
def admin_add_product(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Đã nhập kho sản phẩm mới!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Thêm Sản Phẩm'})

@custom_staff_required
def admin_edit_product(request, pk):
    product = get_object_or_404(Product, id=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Đã cập nhật {product.name}!")
        return redirect('custom_admin_dashboard')
    return render(request, 'core/admin_form.html', {'form': form, 'title': 'Sửa Sản Phẩm', 'product': product})

@custom_staff_required
def admin_delete_product(request, pk):
    if request.user.groups.filter(name='NhanVien').exists():
        messages.error(request, "Bạn không đủ quyền hạn để thực hiện lệnh xoá sản phẩm!")
    else:
        product = get_object_or_404(Product, id=pk)
        product.delete()
        messages.success(request, "Đã xóa sản phẩm khỏi hệ thống!")
    return redirect('custom_admin_dashboard')

# =========================
# 7. QUẢN TRỊ CỬA HÀNG
# =========================

@custom_staff_required
def admin_add_store(request):
    form = StoreForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        new_store = form.save(commit=False)
        location_data = request.POST.get('location')
        if location_data:
            try:
                from django.contrib.gis.geos import GEOSGeometry 
                new_store.location = GEOSGeometry(location_data)
            except (ValueError, TypeError):
                messages.error(request, "Tọa độ không hợp lệ, bản đồ từ chối nhận ghim!")
        
        new_store.save()
        messages.success(request, "Đã khai trương chi nhánh mới và ghim lên bản đồ thành công!")
        return redirect('custom_admin_dashboard')
        
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Thêm Cửa Hàng'})

@custom_staff_required
def admin_add_store(request):
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            
            # Lấy dữ liệu tọa độ từ input ẩn 'location' trên giao diện
            location_data = request.POST.get('location')
            
            if location_data:
                try:
                    # Chuyển chuỗi tọa độ thành đối tượng GIS
                    obj.location = GEOSGeometry(location_data)
                    obj.save() # Lưu thông tin chính của Store
                    
                    # === XỬ LÝ 5 ẢNH BANNER PHỤ ===
                    banners = request.FILES.getlist('banners')
                    if banners:
                        for img in banners:
                            # Thay StoreImage bằng đúng tên Model ảnh phụ của Người
                            StoreImage.objects.create(store=obj, image=img)
                    
                    messages.success(request, "Thêm chi nhánh mới thành công!")
                    return redirect('custom_admin_dashboard')
                    
                except (ValueError, TypeError):
                    messages.error(request, "Tọa độ không hợp lệ! Vui lòng chọn lại trên bản đồ.")
            else:
                # Nếu không có location_data, báo lỗi thay vì để hệ thống crash
                messages.error(request, "Người chưa chọn vị trí chi nhánh trên bản đồ!")
    else:
        form = StoreForm()
    
    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Thêm Cửa Hàng Mới'})

@custom_staff_required
def admin_delete_store(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Chỉ admin mới có quyền đóng cửa chi nhánh!")
    else:
        store = get_object_or_404(Store, id=pk)
        store.delete()
        messages.success(request, "Chi nhánh đã được đóng!")
    return redirect('custom_admin_dashboard')

# =========================
# 8. CHI TIẾT ĐƠN HÀNG & PHÂN QUYỀN
# =========================
@custom_staff_required
def toggle_user_staff(request, user_id):
    """Bật/Tắt quyền truy cập Admin cho người dùng"""
    if request.user.is_superuser:
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user != request.user and not target_user.is_superuser:
            target_user.is_staff = not target_user.is_staff
            target_user.save()
            status = "Admin/Nhân viên" if target_user.is_staff else "Khách hàng"
            messages.success(request, f"Đã chuyển {target_user.username} thành {status}!")
        else:
            messages.error(request, "bạn không thể tác động vào tài khoản cấp cao này!")
    else:
        messages.error(request, "Chỉ admin mới có quyền ban phát chức vị!")
        
    return redirect('custom_admin_dashboard')


@custom_staff_required
def delete_user(request, user_id):
    """Xóa vĩnh viễn tài khoản người dùng"""
    if request.user.is_superuser:
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user == request.user:
            messages.error(request, "bạn không thể tự xóa chính mình!")
        elif target_user.is_superuser:
            messages.error(request, "Không thể xoá một admin khác!")
        else:
            name = target_user.username
            target_user.delete()
            messages.success(request, f" Đã xóa vĩnh viễn tài khoản: {name}")
    else:
        messages.error(request, "bạn không đủ quyền hạn để thực hiện lệnh xoá này!")
        
    return redirect('custom_admin_dashboard')

@custom_staff_required
def admin_order_detail(request, pk):
    order = get_object_or_404(Order, id=pk, complete=True)
    items = order.orderitem_set.all()
    total = sum(i.product.price * i.quantity for i in items if i.product is not None)
    return render(request, 'core/admin_order_detail.html', {
        'order': order, 
        'items': items, 
        'total': total
    })

@custom_staff_required
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
    messages.success(request, f"Đã thăng {target_user.username} thành {role.upper()}!")
    return redirect('custom_admin_dashboard')
@custom_staff_required
def transfer_manager(request):
    if not request.user.is_superuser:
        messages.error(request, "Chỉ admin mới có quyền điều phối nhân sự!")
        return redirect('custom_admin_dashboard')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_store_id = request.POST.get('store_id')
        
        user_to_move = get_object_or_404(User, id=user_id)
        new_store = get_object_or_404(Store, id=new_store_id)

        Store.objects.filter(manager=user_to_move).update(manager=None)
        new_store.manager = user_to_move
        new_store.save()

        messages.success(request, f"Đã điều động {user_to_move.username} về làm Quản lý tại {new_store.name}")
    
    return redirect('custom_admin_dashboard')
def export_inventory_excel(request):
    products = Product.objects.all().values('id', 'name', 'category', 'price', 'stock')
    df = pd.DataFrame(products)
    df.rename(columns={
        'id': 'Mã SP', 
        'name': 'Tên sản phẩm', 
        'category': 'Mã danh mục', 
        'price': 'Giá bán', 
        'stock': 'Tồn kho hiện tại'
    }, inplace=True)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="XuatKho_ONEWAY.xlsx"'
    df.to_excel(response, index=False, engine='openpyxl')
    return response

def import_inventory_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
            count_success = 0
            default_store = getattr(request.user, 'managed_store', None) if not request.user.is_superuser else None

            for index, row in df.iterrows():
                product_id = row.get('Mã SP')
                quantity_added = row.get('Số lượng nhập') 
                
                if pd.notna(product_id) and pd.notna(quantity_added):
                    try:
                        product = Product.objects.get(id=int(product_id))
                        if request.user.is_superuser:
                            store_id_excel = row.get('Mã Chi Nhánh')
                            if pd.isna(store_id_excel):
                                continue 
                            store = Store.objects.get(id=int(store_id_excel))
                        else:
                            store = default_store
                            if not store:
                                continue 
                                
                        inventory, created = Inventory.objects.get_or_create(store=store, product=product)
                        
                        if inventory.quantity is None:
                            inventory.quantity = 0
                            
                        inventory.quantity += int(quantity_added)
                        inventory.save()
                        
                        count_success += 1
                        
                    except (Product.DoesNotExist, Store.DoesNotExist):
                        continue 
                        
            if count_success > 0:
                messages.success(request, f" Đã nhập kho thành công {count_success} dòng dữ liệu!")
            else:
                messages.error(request, "Không nhập được sản phẩm nào. Vui lòng kiểm tra lại Mã SP và Tên cột.")
            
        except Exception as e:
            messages.error(request, f" Lỗi đọc file: {str(e)}")
            
    return redirect(request.META.get('HTTP_REFERER', '/quan-tri/'))

