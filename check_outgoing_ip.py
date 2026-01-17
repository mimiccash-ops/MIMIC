import requests

def get_external_ip():
    print("Перевірка IP-адреси, яку бачить зовнішній світ...")
    try:
        # Використовуємо сервіс ipify для отримання публічної IP
        response = requests.get('https://api.ipify.org?format=json', timeout=10)
        if response.status_code == 200:
            ip_data = response.json()
            print(f"\n✅ ВАШ РЕАЛЬНИЙ ВИХІДНИЙ IP: {ip_data['ip']}")
            return ip_data['ip']
        else:
            print(f"❌ Помилка сервісу: {response.status_code}")
    except Exception as e:
        print(f"❌ Помилка з'єднання: {e}")

    print("\nСпробуйте також цей метод (резервний):")
    try:
        response = requests.get('https://httpbin.org/ip', timeout=10)
        print(f"Результат httpbin: {response.json()['origin']}")
    except Exception as e:
        print(f"Помилка резервного методу: {e}")

if __name__ == "__main__":
    current_ip = get_external_ip()
    
    expected_ip = "38.180.147.102"
    
    if current_ip:
        print("-" * 30)
        if current_ip == expected_ip:
            print("✅ IP збігається з тим, що ви налаштували в Binance.")
            print("👉 Якщо помилка залишається, перевірте 'API Key Permissions' на Binance.")
            print("   Переконайтеся, що галочка 'Enable Futures' (або Spot) увімкнена.")
        else:
            print(f"⚠️ УВАГА: IP НЕ ЗБІГАЄТЬСЯ!")
            print(f"   Ви налаштували: {expected_ip}")
            print(f"   Реальний IP:    {current_ip}")
            print(f"👉 Вам потрібно додати {current_ip} у білий список Binance.")
