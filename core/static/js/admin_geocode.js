window.addEventListener('map:init', function (e) {
    var map = e.detail.map; 
    var addressInput = document.getElementById('id_address');
    var locationInput = document.getElementById('id_location'); // Ô ẩn lưu tọa độ của Django
    var autoMarker = null;

    if (addressInput && locationInput) {
        // 1. TẠO NÚT BẤM KẾ BÊN Ô ĐỊA CHỈ
        var btnGeocode = document.createElement('button');
        btnGeocode.type = 'button'; // Quan trọng: Ngăn nút này submit form
        btnGeocode.innerHTML = '📍 Lấy tọa độ từ Địa chỉ';
        btnGeocode.style.marginLeft = '10px';
        btnGeocode.style.padding = '5px 10px';
        btnGeocode.style.background = '#28a745'; // Màu xanh lá
        btnGeocode.style.color = 'white';
        btnGeocode.style.border = 'none';
        btnGeocode.style.borderRadius = '4px';
        btnGeocode.style.cursor = 'pointer';

        // Gắn nút vào giao diện (ngay sau ô nhập địa chỉ)
        addressInput.parentNode.insertBefore(btnGeocode, addressInput.nextSibling);

        // 2. XỬ LÝ SỰ KIỆN 
        btnGeocode.addEventListener('click', function() {
            var address = addressInput.value;
            
            if (address.trim() === "") {
                alert("bạn chưa nhập địa chỉ vào ô!");
                return;
            }

            // Đổi chữ trên nút thành Đang tìm...
            btnGeocode.innerHTML = '⏳ Đang tìm...';

            var searchQuery = address + ", Vietnam"; 
            var url = 'https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(searchQuery);

            fetch(url)
            .then(response => response.json())
            .then(data => {
                // Trả lại tên nút ban đầu
                btnGeocode.innerHTML = '📍 Lấy tọa độ từ Địa chỉ';

                if (data.length > 0) {
                    var lat = parseFloat(data[0].lat);
                    var lon = parseFloat(data[0].lon);

                    // A. Bay bản đồ đến vị trí đó
                    map.flyTo([lat, lon], 17);

                    // B. GHI DỮ LIỆU TỌA ĐỘ VÀO DJANGO (Để hết lỗi No geometry)
                    var pointGeoJSON = {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    };
                    locationInput.value = JSON.stringify(pointGeoJSON);

                    // C. Cắm cờ xanh lên bản đồ xem trước
                    if (autoMarker !== null) {
                        map.removeLayer(autoMarker);
                    }
                    autoMarker = L.marker([lat, lon]).addTo(map);
                    autoMarker.bindPopup("Vị trí của: " + address).openPopup();
                    
                    alert("Đã ghim tọa độ! có thể bấm LƯU ở dưới cùng ngay bây giờ.");

                } else {
                    alert("Không tìm thấy tọa độ tự động. vui lòng dùng thanh công cụ bên trái bản đồ để tự chấm điểm nhé!");
                }
            })
            .catch(err => {
                console.error(err);
                btnGeocode.innerHTML = '📍 Lấy tọa độ từ Địa chỉ';
                alert("Lỗi mạng khi tìm kiếm!");
            });
        });
    }
});