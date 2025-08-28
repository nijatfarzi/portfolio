import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Rastgele veri üretme ayarları
np.random.seed(42)  # Tutarlılık için
customer_count = 500  # 500 benzersiz müşteri
order_count = 10000   # Toplam 10K sipariş

# Müşteri ID'leri oluştur
customer_ids = [f"CUST_{i:05d}" for i in range(1, customer_count + 1)]

# Rastgele tarihler (son 2 yıl içinde)
start_date = datetime.now() - timedelta(days=730)
end_date = datetime.now()

# Ürün kategorileri
categories = ["Electronics", "Clothing", "Home", "Books", "Groceries"]

# Veri setini oluştur
data = {
    "customer_id": np.random.choice(customer_ids, order_count),
    "order_date": [start_date + timedelta(days=random.randint(0, 730)) for _ in range(order_count)],
    "order_amount": np.round(np.random.lognormal(mean=3, sigma=0.5, size=order_count), 2),
    "product_category": np.random.choice(categories, order_count),
    "customer_acquisition_cost": np.random.uniform(10, 100, order_count),  # CAC için
    "profit_margin": np.random.uniform(0.1, 0.4, order_count)  # CLV için
}

# DataFrame'e çevir
df = pd.DataFrame(data)

# CSV olarak kaydet
df.to_csv("customer_analytics_data.csv", index=False)
print("CSV oluşturuldu: customer_analytics_data.csv")