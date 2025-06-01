import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta

# Fake veri üretmek için
fake = Faker()

# Rastgelelik için seed
np.random.seed(42)

# 5000 satır veri oluştur
num_rows = 5000

# Kanal ve kampanya isimleri
channels = ["Google Ads", "Facebook", "Instagram", "Email", "Organic", "Twitter", "Affiliate"]
campaigns = ["Summer Sale", "Black Friday", "New Product", "Holiday Discount", "Brand Awareness"]

# Tarih aralığı (son 1 yıl)
dates = [datetime.now() - timedelta(days=np.random.randint(1, 365)) for _ in range(num_rows)]

# Veri çerçevesi
data = {
    "Date": dates,
    "Channel": np.random.choice(channels, num_rows, p=[0.25, 0.2, 0.15, 0.1, 0.15, 0.1, 0.05]),
    "Campaign": np.random.choice(campaigns, num_rows),
    "Spend (TL)": np.round(np.random.uniform(50, 5000, num_rows), 2),
    "Impressions": np.random.randint(1000, 100000, num_rows),
    "Clicks": np.random.randint(50, 5000, num_rows),
    "Acquired_Customers": np.random.randint(1, 100, num_rows),
    "Revenue (TL)": np.round(np.random.uniform(100, 20000, num_rows), 2),
    "Product_Cost (TL)": np.round(np.random.uniform(20, 5000, num_rows), 2),
}

df = pd.DataFrame(data)

# ROI ve CAC hesaplamaları
df["ROI (%)"] = np.round(((df["Revenue (TL)"] - df["Product_Cost (TL)"] - df["Spend (TL)"]) / df["Spend (TL)"]) * 100, 2)
df["CAC (TL)"] = np.round(df["Spend (TL)"] / df["Acquired_Customers"], 2)

# Tarih formatı
df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

# CSV'ye kaydet
df.to_csv("roi_cac_analysis_data.csv", index=False, encoding="utf-8")

print("✅ 5000 satırlık CSV oluşturuldu: roi_cac_analysis_data.csv")