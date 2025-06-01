# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta

# # Rastgele veri üretimi
# np.random.seed(42)
# user_ids = [f"user_{i}" for i in range(1, 1001)]
# events = ["homepage_view", "product_click", "cart_add", "checkout_start", "purchase_complete"]
# devices = ["mobile", "desktop", "tablet"]

# data = []
# for _ in range(10000):
#     user = np.random.choice(user_ids)
#     session = f"session_{np.random.randint(1, 100)}"
#     event = np.random.choice(events, p=[0.4, 0.3, 0.15, 0.1, 0.05])  # Event olasılıkları
#     device = np.random.choice(devices)
#     duration = np.random.randint(5, 180)
#     timestamp = datetime.now() - timedelta(days=np.random.randint(1, 30), 
#                                          hours=np.random.randint(1, 24))
#     page_url = f"https://example.com/{event.split('_')[0]}"
#     data.append([user, timestamp, event, session, device, page_url, duration])

# df = pd.DataFrame(data, columns=["user_id", "timestamp", "event_name", "session_id", "device", "page_url", "duration"])
# df.to_csv("funnel_data.csv", index=False)
# print("CSV oluşturuldu: funnel_data.csv")

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Veri boyutu
n_rows = 10000

# Rastgele veri üretme fonksiyonları
def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def random_device():
    return random.choice(['mobile', 'desktop', 'tablet'])

def random_channel():
    return random.choice(['organic', 'direct', 'social', 'email', 'referral', 'paid'])

def random_location():
    cities = ['Istanbul', 'Ankara', 'Izmir', 'Bursa', 'Antalya', 'Adana', 'Konya', 'Gaziantep']
    return random.choice(cities)

def random_page():
    pages = ['home', 'product', 'cart', 'checkout', 'payment', 'confirmation', 'login', 'register']
    return random.choice(pages)

def random_event():
    events = ['page_view', 'add_to_cart', 'checkout_start', 'payment', 'login', 'register', 'search']
    return random.choice(events)

# User ID'ler oluştur (500 benzersiz kullanıcı)
user_ids = [f"user_{i}" for i in range(1, 501)]
user_data = {uid: {
    'abone': random.choice([True, False]),
    'satis': random.choice([True, False]),
    'churn': random.choice([True, False])
} for uid in user_ids}

# Zaman aralığı (son 90 gün)
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

# Veri oluşturma
data = []
for _ in range(n_rows):
    user_id = random.choice(user_ids)
    user_info = user_data[user_id]
    timestamp = random_date(start_date, end_date)
    session_id = f"session_{random.randint(1000, 9999)}"
    
    row = {
        'user_id': user_id,
        'abone': user_info['abone'],
        'satis': user_info['satis'],
        'churn': user_info['churn'],
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'event_name': random_event(),
        'session_id': session_id,
        'device': random_device(),
        'page_url': random_page(),
        'channel': random_channel(),
        'location': random_location()
    }
    data.append(row)

# DataFrame oluştur
df = pd.DataFrame(data)

# Sıralama (timestamp'e göre)
df = df.sort_values('timestamp')

# CSV'ye kaydet
df.to_csv('funnel_persona_dataset.csv', index=False)

print("Dataset başarıyla oluşturuldu: funnel_persona_dataset.csv")
print(f"Toplam satır: {len(df)}")
print(f"Benzersiz kullanıcı: {df['user_id'].nunique()}")
print(f"Zaman aralığı: {df['timestamp'].min()} - {df['timestamp'].max()}")
