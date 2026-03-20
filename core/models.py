from django.contrib.gis.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên sản phẩm")
    price = models.IntegerField(verbose_name="Giá bán")
    image_url = models.URLField(blank=True, null=True, verbose_name="Link ảnh")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")

    def __str__(self):
        return self.name

class Store(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên cửa hàng")
    address = models.CharField(max_length=500, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại")
    
    # ĐÂY LÀ TRƯỜNG QUAN TRỌNG NHẤT CỦA ĐỒ ÁN GIS
    # PointField dùng để lưu Tọa độ (Kinh độ, Vĩ độ) của cửa hàng
    # srid=4326 là hệ tọa độ chuẩn của Google Maps / OpenStreetMap
    location = models.PointField(srid=4326, verbose_name="Tọa độ cửa hàng")

    def __str__(self):
        return self.name
class Order(models.Model):
    # Trạng thái complete=False nghĩa là đang nằm trong giỏ, chưa thanh toán
    complete = models.BooleanField(default=False, verbose_name="Đã thanh toán")
    date_ordered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Đơn hàng {self.id}"

    # Hàm ORM tự động tính tổng tiền của cả giỏ hàng
    @property
    def get_cart_total(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.get_total for item in orderitems])
        return total

class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="Sản phẩm")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, verbose_name="Đơn hàng")
    quantity = models.IntegerField(default=0, null=True, blank=True, verbose_name="Số lượng")

    # Hàm ORM tự động tính tiền của từng món (Giá x Số lượng)
    @property
    def get_total(self):
        total = self.product.price * self.quantity
        return total
class Review(models.Model):
    # Tất cả các dòng dưới đây đều phải thụt vào 1 Tab nhé!
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Dòng return này lại nằm trong hàm def, nên phải thụt thêm 1 Tab nữa
        return f"{self.user.username} đánh giá {self.product.name} ({self.rating} Sao)"