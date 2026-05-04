from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid # Để tạo mã đơn hàng tự động
from ckeditor_uploader.fields import RichTextUploadingField

# ==========================================
# 1. SẢN PHẨM & PHÂN LOẠI
# ==========================================
class Product(models.Model):
    CATEGORY_CHOICES = [
        ('phone', 'Điện thoại, Tablet'),
        ('laptop', 'Laptop, Macbook'),
        ('ipad', 'iPad, Máy tính bảng'),
        ('am-thanh', 'Âm thanh, Tai nghe'),
        ('phu-kien', 'Phụ kiện công nghệ'),
    ]
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Giá tiền")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='phone', verbose_name="Loại sản phẩm")
    brand = models.CharField(max_length=50, null=True, blank=True, verbose_name="Thương hiệu")
    
    # Ảnh sản phẩm
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    image_2 = models.ImageField(upload_to='products/', null=True, blank=True)
    image_3 = models.ImageField(upload_to='products/', null=True, blank=True)
    image_4 = models.ImageField(upload_to='products/', null=True, blank=True)
    image_5 = models.ImageField(upload_to='products/', null=True, blank=True)
    description = RichTextUploadingField(verbose_name="Mô tả chi tiết", null=True, blank=True)
    desc_image = models.ImageField(upload_to='products/desc/', null=True, blank=True)

    @property
    def get_image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return "https://via.placeholder.com/300x300?text=ONEWAY+Product"

    def __str__(self):
        return self.name

# ==========================================
# 2. CỬA HÀNG & TRẠNG THÁI GIS
# ==========================================
class Store(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=500)
    phone = models.CharField(max_length=20, blank=True, null=True)
    description = RichTextUploadingField(verbose_name="Mô tả chi tiết", blank=True, null=True)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    rating = models.FloatField(default=5.0)
    location = models.PointField(srid=4326) 
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to='stores/', blank=True, null=True, verbose_name="Ảnh chính")
    image_2 = models.ImageField(upload_to='stores/', blank=True, null=True, verbose_name="Ảnh Poster 2")
    image_3 = models.ImageField(upload_to='stores/', blank=True, null=True, verbose_name="Ảnh Poster 3")
    promotion_text = RichTextUploadingField(blank=True, null=True, verbose_name="Chương trình ưu đãi")

    manager = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_store',
        verbose_name="Quản lý chi nhánh"
    )

    def __str__(self):
        return self.name
    @property
    def get_image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return "https://via.placeholder.com/400x200?text=ONEWAY+Store"

    @property
    def is_open(self):
        if not self.opening_time or not self.closing_time:
            return True 
        now = timezone.localtime().time()
        return self.opening_time <= now <= self.closing_time
class StoreImage(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='stores/gallery/', verbose_name="Ảnh Slide")

    def __str__(self):
        return f"Ảnh slide của {self.store.name}"
# ==========================================
# 3. QUẢN LÝ TỒN KHO (MỚI)
# ==========================================
class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng tồn")

    class Meta:
        verbose_name_plural = "Tồn kho chi nhánh"
        unique_together = ('product', 'store')

    def __str__(self):
        return f"{self.product.name} - {self.store.name}: {self.quantity}"

# ==========================================
# 4. PHÂN QUYỀN NHÂN VIÊN CHI NHÁNH (MỚI)
# ==========================================
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    assigned_store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Làm việc tại chi nhánh")
    is_manager = models.BooleanField(default=False, verbose_name="Quyền quản lý chi nhánh")

    def __str__(self):
        return f"{self.user.username} - {self.assigned_store.name if self.assigned_store else 'Vãng lai'}"

# ==========================================
# 5. ĐƠN HÀNG & VẬN CHUYỂN
# ==========================================
class Order(models.Model):
    ORDER_TYPE = (('online', 'Mua Online'), ('counter', 'Tại quầy'))
    STATUS = (('pending', 'Chờ xử lý'), ('shipping', 'Đang giao'), ('completed', 'Hoàn tất'), ('cancelled', 'Đã hủy'))

    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    order_code = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE, default='online')
    status = models.CharField(max_length=15, choices=STATUS, default='pending')
    assigned_store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True)
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    distance_km = models.FloatField(default=0, verbose_name="Khoảng cách giao hàng (km)")

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = f"OW-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_code} - {self.get_order_type_display()}"

    @property
    def get_cart_total(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.get_total for item in orderitems])
        return Decimal(total) + self.shipping_fee

class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField(default=0, null=True, blank=True)

    @property
    def get_total(self):
        return (self.product.price if self.product else 0) * self.quantity

# ==========================================
# 6. ĐÁNH GIÁ
# ==========================================
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'product')

# ==========================================
# 7. QUẢN LÝ TRANG GIỚI THIỆU
# ==========================================
class CompanyInfo(models.Model):
    title = models.CharField(max_length=200, default="Giới thiệu Oneway Store")
    description = models.TextField(blank=True, null=True)

class CompanyImage(models.Model):
    info = models.ForeignKey(CompanyInfo, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='company_images/')
    is_banner = models.BooleanField(default=True) 