import os
import urllib.request
import subprocess
import argparse
import geoip2.database

def download_geoip_db(db_url, db_path):
    if os.path.exists(db_path):
        print(f"\033[93mУдаление старой базы данных:\033[0m {db_path}")
        os.remove(db_path)
    print(f"\033[92mСкачивание базы данных из\033[0m {db_url}...")
    urllib.request.urlretrieve(db_url, db_path)
    print("\033[92mЗагрузка завершена.\033[0m")

def download_file(url, path):
    import requests
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Файл {path} загружен.")
    else:
        print(f"Ошибка загрузки {url}: {response.status_code}")

def lookup_ip(ip):
    global city_db_path, asn_db_path
    with geoip2.database.Reader(city_db_path) as city_reader, geoip2.database.Reader(asn_db_path) as asn_reader:
        try:
            city_data = city_reader.city(ip)
            asn_data = asn_reader.asn(ip)
            result = {
                "IP": ip,
                "Страна": city_data.country.name if city_data.country.name else "Unknown Country",
                "Город": city_data.city.name if city_data.city.name else "Unknown City",
                "ASN": asn_data.autonomous_system_number,
                "Провайдер": asn_data.autonomous_system_organization,
            }
        except Exception as e:
            result = {"IP": ip, "Ошибка": str(e)}
    return result

def get_inbound_ips(port):
    command = (
        f"netstat -tn | awk -v port={port} '$6==\"ESTABLISHED\" {{"
        f" split($4, local, \":\"); if(local[2]==port) print $5 }}' | cut -d: -f1 | sort -u"
    )
    try:
        result = subprocess.check_output(command, shell=True, text=True)
        ips = result.strip().split("\n")
        ips = [ip for ip in ips if ip]
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды для входящих соединений: {e}")
        ips = []
    return ips

def get_outbound_ips(port):
    command = (
        f"netstat -tn | awk -v port={port} '$6==\"ESTABLISHED\" {{"
        f" split($5, remote, \":\"); if(remote[2]==port) print $5 }}' | cut -d: -f1 | sort -u"
    )
    try:
        result = subprocess.check_output(command, shell=True, text=True)
        ips = result.strip().split("\n")
        ips = [ip for ip in ips if ip]
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды для исходящих соединений: {e}")
        ips = []
    return ips

def is_package_installed(package_name):
    result = subprocess.run(
        ["dpkg", "-l", package_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.returncode == 0

city_db_path = "/tmp/GeoLite2-City.mmdb"
asn_db_path = "/tmp/GeoLite2-ASN.mmdb"
city_db_url = "https://git.io/GeoLite2-City.mmdb"
asn_db_url = "https://git.io/GeoLite2-ASN.mmdb"

if __name__ == "__main__":
    packages = ["python3-geoip2", "net-tools"]
    packages_to_install = [pkg for pkg in packages if not is_package_installed(pkg)]
    
    if packages_to_install:
        print(f"Устанавливаю: {' '.join(packages_to_install)}")
        subprocess.run(["apt", "install", "-y"] + packages_to_install, check=True)
    else:
        print("Необходимые пакеты установлены.")

    
    
    parser = argparse.ArgumentParser(description="Получение информации по IP из ESTABLISHED соединений")
    parser.add_argument("--port", type=int, default=443,
                        help="Порт для фильтрации ESTABLISHED соединений (по умолчанию 443)")
    args = parser.parse_args()
    
    # Скачиваем базы данных GeoLite2
    download_geoip_db(city_db_url, city_db_path)
    download_geoip_db(asn_db_url, asn_db_path)
    
    print("=== Входящие соединения ===")
    inbound_ips = get_inbound_ips(args.port)
    if not inbound_ips:
        print(f"Нет входящих соединений на порту {args.port}.")
    for ip in inbound_ips:
        data = lookup_ip(ip)
        if "Ошибка" in data:
            print(f"IP: {ip} (Ошибка: {data['Ошибка']})")
        else:
            # Если город неизвестен, выводим без него
            if data["Город"] == "Unknown City":
                print(f"IP: {data['IP']} ({data['Страна']}, AS{data['ASN']} {data['Провайдер']})")
            else:
                print(f"IP: {data['IP']} ({data['Страна']}, {data['Город']}, AS{data['ASN']} {data['Провайдер']})")
    
    print("\n=== Исходящие соединения ===")
    outbound_ips = get_outbound_ips(args.port)
    if not outbound_ips:
        print(f"Нет исходящих соединений на порту {args.port}.")
    for ip in outbound_ips:
        data = lookup_ip(ip)
        if "Ошибка" in data:
            print(f"IP: {ip} (Ошибка: {data['Ошибка']})")
        else:
            if data["Город"] == "Unknown City":
                print(f"IP: {data['IP']} ({data['Страна']}, AS{data['ASN']} {data['Провайдер']})")
            else:
                print(f"IP: {data['IP']} ({data['Страна']}, {data['Город']}, AS{data['ASN']} {data['Провайдер']})")
