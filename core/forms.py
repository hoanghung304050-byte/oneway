from django import forms
from .models import Product, Store

class ProductForm(forms.ModelForm):
    # 1. Định nghĩa field price tùy chỉnh (Vẫn giữ nguyên ý đồ của đại vương)
    price = forms.CharField(
        label="Giá bán",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ví dụ: 25.190.000đ',
            'id': 'price_input'
        })
    )

    class Meta:
        model = Product # Đã đưa vào trong class ProductForm
        # Danh sách fields khớp với models.py mới (dùng image thay cho image_url)
        fields = [
            'name', 'price', 'category', 'brand', 
            'image', 'image_2', 'image_3', 'image_4', 'image_5', 
            'description', 'desc_image'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Apple, Samsung...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            # Với ImageField, ngài không cần dùng URLInput nữa, 
            # hãy để Django tự tạo nút "Chọn tệp" cho ngài.
        }

    # 2. Hàm "Gọt rửa" dữ liệu (Phải thụt lề vào trong class ProductForm)
    def clean_price(self):
        data = self.cleaned_data['price']
        # Loại bỏ các ký tự thừa
        clean_data = data.replace('.', '').replace(',', '').replace('đ', '').replace(' ', '')
        
        try:
            return int(clean_data)
        except ValueError:
            raise forms.ValidationError("Ngài vui lòng chỉ nhập số và dấu chấm phân cách!")

    # 3. Hàm khởi tạo (Phải thụt lề vào trong class ProductForm)
    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Định dạng lại số 25190000 thành 25.190.000 để hiện lên ô nhập khi SỬA
            self.initial['price'] = f"{self.instance.price:,.0f}".replace(',', '.')


class StoreForm(forms.ModelForm):
    location = forms.CharField(widget=forms.HiddenInput(), required=False)
    class Meta:
        model = Store
        fields = [
            'name', 'address', 'phone', 'description', 
            'opening_time', 'closing_time', 'rating', 
            'image', 'location'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'}),
            'opening_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'closing_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Nhập vài dòng giới thiệu...'}),
        }