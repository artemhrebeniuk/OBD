#!/usr/bin/env python3
import sys
import time
import random

try:
    import serial
except ImportError:
    print("Ошибка: Для работы эмулятора требуется библиотека pyserial!")
    print("Установите её командой: pip install pyserial")
    sys.exit(1)

def format_obd_response(payload, headers, spaces):
    """
    Форматирует OBD-ответ с учетом настроек заголовков (headers) и пробелов (spaces).
    Для CAN протокола (ID 6) заголовок имеет вид: 7E8 <размер_данных_в_hex> <данные>
    """
    if headers:
        num_bytes = len(payload.split())
        formatted = f"7E8 {num_bytes:02X} {payload}"
    else:
        formatted = payload

    if not spaces:
        formatted = formatted.replace(" ", "")
    return formatted

def main():
    if len(sys.argv) < 2:
        print("Использование: python elm_emulator.py <COM_PORT>")
        print("Пример: python elm_emulator.py COM3")
        sys.exit(1)

    port = sys.argv[1]
    baudrate = 38400

    print(f"=== Запуск эмулятора ELM327 на порту {port} ({baudrate} baud) ===")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except Exception as e:
        print(f"Не удалось открыть порт {port}: {e}")
        print("Убедитесь, что порт не занят другой программой и com0com настроен корректно.")
        sys.exit(1)

    print("Эмулятор успешно запущен и ожидает подключений...")
    
    buffer = ""
    
    # Состояние протокола ELM327
    spaces = True
    echo = True
    headers = False  # По умолчанию в ELM327 заголовки выключены
    
    # Исходные значения для симуляции
    speed = 60
    rpm = 2500
    battery = 88.0
    voltage = 14.2
    ambient = 18.0

    try:
        while True:
            if ser.in_waiting > 0:
                char = ser.read().decode('utf-8', errors='ignore')
                buffer += char
                
                if char == '\r':
                    cmd_raw = buffer.replace('\r', '').replace('\n', '')
                    cmd = cmd_raw.strip().replace(" ", "").upper()
                    buffer = ""
                    
                    if not cmd:
                        ser.write(b"\r>")
                        continue
                    
                    print(f"Получена команда: '{cmd_raw}' -> '{cmd}' (echo={echo}, headers={headers}, spaces={spaces})")
                    
                    # Симуляция изменения данных
                    speed = max(0, min(220, speed + random.randint(-2, 2)))
                    rpm = max(800, min(7500, rpm + random.randint(-100, 100)))
                    battery = max(0.0, min(100.0, battery - 0.01))
                    voltage = max(11.5, min(14.8, voltage + random.uniform(-0.05, 0.05)))
                    ambient = max(15.0, min(25.0, ambient + random.uniform(-0.1, 0.1)))

                    # Эхо команды, если включено
                    if echo:
                        ser.write((cmd_raw + "\r").encode('utf-8'))

                    # Определение ответа
                    response_text = ""
                    is_obd = False
                    
                    # AT-команды ELM327
                    if cmd == "ATZ":
                        response_text = "ELM327 v1.5"
                        # Сброс настроек
                        echo = True
                        spaces = True
                        headers = False
                    elif cmd == "ATE0":
                        echo = False
                        response_text = "OK"
                    elif cmd == "ATE1":
                        echo = True
                        response_text = "OK"
                    elif cmd == "ATH0":
                        headers = False
                        response_text = "OK"
                    elif cmd == "ATH1":
                        headers = True
                        response_text = "OK"
                    elif cmd == "ATS0":
                        spaces = False
                        response_text = "OK"
                    elif cmd == "ATS1":
                        spaces = True
                        response_text = "OK"
                    elif cmd.startswith("ATL") or cmd.startswith("ATM"):
                        response_text = "OK"
                    elif cmd.startswith("ATSP"):
                        response_text = "OK"
                    elif cmd == "ATDP":
                        response_text = "ISO 15765-4 (CAN 11/500)"
                    elif cmd == "ATDPN":
                        response_text = "6"  # ISO 15765-4 (CAN 11/500)
                    elif cmd.startswith("ATTP"):
                        response_text = "OK"
                    elif cmd == "ATRV":
                        response_text = f"{voltage:.1f}V"
                    
                    # OBD-II PIDs (Mode 01)
                    elif cmd == "0100":
                        response_text = "41 00 BE 3E A8 13"
                        is_obd = True
                    elif cmd == "0120":
                        response_text = "41 20 80 00 00 00"
                        is_obd = True
                    elif cmd == "0140":
                        response_text = "41 40 48 00 00 00"
                        is_obd = True
                    elif cmd == "0160":
                        response_text = "41 60 00 00 00 00"
                        is_obd = True
                    
                    elif cmd == "010C":
                        raw_val = int(rpm * 4)
                        a = (raw_val >> 8) & 0xFF
                        b = raw_val & 0xFF
                        response_text = f"41 0C {a:02X} {b:02X}"
                        is_obd = True
                    elif cmd == "010D":
                        response_text = f"41 0D {int(speed):02X}"
                        is_obd = True
                    elif cmd == "0142":
                        raw_val = int(voltage * 1000)
                        a = (raw_val >> 8) & 0xFF
                        b = raw_val & 0xFF
                        response_text = f"41 42 {a:02X} {b:02X}"
                        is_obd = True
                    elif cmd == "0146":
                        raw_val = int(ambient + 40)
                        response_text = f"41 46 {raw_val:02X}"
                        is_obd = True
                    elif cmd == "015B":
                        raw_val = int(battery * 255 / 100)
                        response_text = f"41 5B {raw_val:02X}"
                        is_obd = True
                    else:
                        response_text = "NO DATA"
                    
                    # Форматируем OBD ответ (заголовки и пробелы)
                    if is_obd:
                        full_response = format_obd_response(response_text, headers, spaces) + "\r>"
                    else:
                        # Для обычных AT-команд пробелы и заголовки не меняются
                        full_response = response_text + "\r>"
                        
                    ser.write(full_response.encode('utf-8'))
                    print(f"Отправлен ответ: {full_response.replace('\r', '\\r')}")
                    
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nЗавершение работы эмулятора по запросу пользователя.")
    finally:
        ser.close()
        print("Порт закрыт.")

if __name__ == "__main__":
    main()
