import os

# Alapértelmezett SSID, de Render-en érdemes az Environment Variables-ből (Környezeti változók) beolvasni.
# Ha nincs beállítva környezeti változó a Renderen, akkor ezt a lenti értéket fogja használni.
SSID = os.getenv("PO_SSID", '42["auth",{"session":"5t9fvor16dn4q5ua38goi9uon0","isDemo":1,"uid":29950520,"platform":2,"isFastHistory":true,"isOptimized":true}]')

# Alapértelmezett párok
PAIRS = [
    # Forex OTC
    "EURUSD_otc",
    "GBPUSD_otc",
    "USDJPY_otc",
    "AUDUSD_otc",
    "EURGBP_otc",
    "EURJPY_otc",
    "GBPJPY_otc",
    "USDCHF_otc",

    # Crypto OTC
    "BTCUSD_otc",
    "ETHUSD_otc",
    "LTCUSD_otc",
    "XRPUSD_otc",
]