from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Tên điện thoại")
    price = models.IntegerField(verbose_name="Giá bán (VND)")
    # Tạm thời dùng link ảnh web để thao tác nhanh, sau này có thể đổi sang models.ImageField
    image = models.ImageField(upload_to='product/', blank=True, null=True, verbose_name="Link ảnh") 
    description = models.TextField(blank=True, verbose_name="Mô tả tóm tắt")

    def __str__(self):
        return self.name