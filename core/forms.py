from django import forms
from .models import Product, Store

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__' # Lấy tất cả các cột trong bảng Product
        
        # Nhúng class của Bootstrap vào để giao diện đẹp luôn
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên điện thoại'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'image_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Link ảnh sản phẩm'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'phone', 'address', 'location']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: ONEWAY Quận 1'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'id': 'store_address', 'placeholder': 'Nhập địa chỉ chi tiết'}),
            # Quan trọng: Ẩn ô location đi, chúng ta sẽ dùng JavaScript để điền tọa độ vào đây!
            'location': forms.TextInput(attrs={'id': 'store_location', 'type': 'hidden'}),
        }