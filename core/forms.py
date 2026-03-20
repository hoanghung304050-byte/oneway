from django import forms
from .models import Product, Store

class ProductForm(forms.ModelForm):
    # Chuyển price sang CharField để chấp nhận nhập dấu chấm và chữ 'đ'
    price = forms.CharField(
        label="Giá bán",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ví dụ: 25.190.000đ',
            'id': 'price_input'
        })
    )

    class Meta:
        model = Product
        fields = '__all__'

    # === HÀM "GỌT RỬA" DỮ LIỆU TRƯỚC KHI LƯU ===
    def clean_price(self):
        data = self.cleaned_data['price']
        
        # Loại bỏ tất cả dấu chấm, dấu phẩy và chữ 'đ'
        clean_data = data.replace('.', '').replace(',', '').replace('đ', '').replace(' ', '')
        
        try:
            # Chuyển về kiểu số nguyên để lưu vào Database
            return int(clean_data)
        except ValueError:
            raise forms.ValidationError("Ngài vui lòng chỉ nhập số và dấu chấm phân cách!")

    # Hàm khởi tạo để hiển thị lại giá có dấu chấm khi ngài bấm SỬA sản phẩm
    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Định dạng lại số 25190000 thành 25.190.000 để hiện lên ô nhập
            self.initial['price'] = f"{self.instance.price:,.0f}".replace(',', '.')
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