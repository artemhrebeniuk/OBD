#!/usr/bin/env python3
"""
OBD-II Dashboard — кроссплатформенное приложение (macOS / Windows).

Использует:
  • PyQt5 — графический интерфейс (надежная отрисовка на всех ОС)
  • python-obd (obd.Async) — асинхронное чтение данных с ELM327
  • Pint (через obd.Unit) — конвертация и отображение величин

Автор: @mr_shpepe
"""

import sys
import os
import random
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

# ---------------------------------------------------------------------------
#  Настройка логирования
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # Если запущено как скомпилированный .exe/.app файл
    base_dir = os.path.dirname(sys.executable)
else:
    # Если запущено как обычный скрипт .py
    base_dir = os.path.dirname(os.path.abspath(__file__))

log_file = os.path.join(base_dir, "obd_dashboard.log")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Подавляем предупреждения от библиотек python-obd и pint
logging.getLogger("pint").setLevel(logging.ERROR)
logging.getLogger("obd").setLevel(logging.ERROR)   # убираем шум от внутренностей python-obd


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSizePolicy, QCheckBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QRectF
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QPainter, QPen, QConicalGradient, QBrush
)

# ---------------------------------------------------------------------------
#  Импорт библиотеки OBD
# ---------------------------------------------------------------------------
try:
    import obd
    from obd import OBDStatus
    OBD_AVAILABLE = True
except ImportError:
    OBD_AVAILABLE = False
    logger.warning("Библиотека python-obd не установлена. Реальный режим будет недоступен.")

# ---------------------------------------------------------------------------
#  Очередь сигналов (потокобезопасная передача в GUI)
# ---------------------------------------------------------------------------
class UISignals(QObject):
    # Сигналы для обновления значений
    speed_updated = pyqtSignal(str)
    rpm_updated = pyqtSignal(str)
    
    # Сигналы статуса
    connect_ok = pyqtSignal(str, str)     # status, port
    connect_fail = pyqtSignal(str)        # error_msg
    hw_disconnect = pyqtSignal(str)       # error_msg
    
    # Сигналы для EV и динамической панели
    battery_updated = pyqtSignal(str)
    voltage_updated = pyqtSignal(str)
    ambient_updated = pyqtSignal(str)
    auto_switch_gauge = pyqtSignal(int)

# ---------------------------------------------------------------------------
#  Кастомный выпадающий список для автообновления COM-портов при клике
# ---------------------------------------------------------------------------
class PortComboBox(QComboBox):
    def __init__(self, parent_app, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app

    def showPopup(self):
        try:
            self.parent_app._refresh_ports()
        except Exception as e:
            logger.error("Ошибка при обновлении портов при открытии списка: %s", e)
        super().showPopup()

# ---------------------------------------------------------------------------
#  Виджет круговой шкалы (Gauge)
# ---------------------------------------------------------------------------
class CircularGauge(QWidget):
    """
    Виджет круговой шкалы (Gauge).
    Отрисовывает красивую спидометро-подобную шкалу с помощью QPainter.
    Поддерживает динамическое изменение цвета с помощью градиентов.
    """
    clicked = pyqtSignal()

    def __init__(self, title, unit, max_value=100.0, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.max_value = float(max_value)
        self.current_value_num = 0.0
        self.current_value_str = "—"
        
        self.setMinimumSize(250, 250)
        self.setCursor(Qt.PointingHandCursor)
        
    def configure(self, title, unit, max_value):
        self.title = title
        self.unit = unit
        self.max_value = float(max_value)
        self.current_value_num = 0.0
        self.current_value_str = "—"
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
        
    def set_value(self, val_str: str):
        if val_str in ("—", "ERR"):
            self.current_value_str = val_str
            self.current_value_num = 0.0
        else:
            try:
                val = float(val_str)
                self.current_value_num = min(val, self.max_value)
                # Форматируем число с запятой (тысячные разделители)
                if val.is_integer():
                    self.current_value_str = f"{int(val):,}"
                else:
                    self.current_value_str = f"{val:,.1f}"
            except ValueError:
                self.current_value_str = val_str
                self.current_value_num = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        size = min(width, height)
        
        # Квадрат для отрисовки дуги
        margin = 30
        rect = QRectF(
            (width - size) / 2 + margin,
            (height - size) / 2 + margin,
            size - margin * 2,
            size - margin * 2
        )
        
        # 1. Фоновая дуга (Track)
        pen_bg = QPen(QColor("#121221"))
        pen_bg.setWidth(16)
        pen_bg.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_bg)
        
        start_angle = 225 * 16
        span_angle = -270 * 16
        painter.drawArc(rect, start_angle, span_angle)
        
        # 2. Активная дуга (Градиент)
        if self.current_value_str not in ("—", "ERR") and self.max_value > 0:
            progress = self.current_value_num / self.max_value
            active_span_angle = int(-270 * 16 * progress)
            
            # Конический градиент
            gradient = QConicalGradient(rect.center(), -45)
            gradient.setColorAt(0.0, QColor("#ff1744"))   
            gradient.setColorAt(0.375, QColor("#7c4dff")) 
            gradient.setColorAt(0.75, QColor("#00d4ff"))  
            gradient.setColorAt(1.0, QColor("#00d4ff"))   
            
            pen_fg = QPen(QBrush(gradient), 16.0)
            pen_fg.setCapStyle(Qt.RoundCap)
            painter.setPen(pen_fg)
            painter.drawArc(rect, start_angle, active_span_angle)
            
        # 3. Текст значения (отцентрован)
        painter.setPen(QColor("#ffffff"))
        font_val = QFont("Helvetica", 72, QFont.Bold)
        painter.setFont(font_val)
        val_rect = rect.adjusted(0, -25, 0, -25)
        painter.drawText(val_rect, Qt.AlignCenter, self.current_value_str)
        
        # 4. Текст единицы измерения
        painter.setPen(QColor("#859398"))
        font_unit = QFont("Courier New", 14, QFont.Bold)
        font_unit.setLetterSpacing(QFont.PercentageSpacing, 110)
        painter.setFont(font_unit)
        unit_rect = rect.adjusted(0, 45, 0, 45)
        painter.drawText(unit_rect, Qt.AlignCenter, self.unit)

# ---------------------------------------------------------------------------
#  Главный класс окна
# ---------------------------------------------------------------------------
class OBDApp(QMainWindow):
    """
    Главный класс окна приложения. 
    Отвечает за отрисовку всего графического интерфейса, 
    управление режимами (LIVE / SIMULATION) и обработку событий.
    Взаимодействует с фоновыми потоками OBD через систему сигналов Qt (UISignals).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBD-II Dashboard")
        self.resize(1000, 600)
        
        # Состояние
        self.connection = None
        self._connected = False
        self._connecting = False
        self._connect_attempt_id = 0
        self.simulation_mode = False  # Динамический режим (по умолчанию LIVE)
        
        # Сигналы (связываем события фонового потока с методами GUI)
        self.signals = UISignals()
        self.signals.speed_updated.connect(self._on_speed_ui)
        self.signals.rpm_updated.connect(self._on_rpm_ui)
        self.signals.battery_updated.connect(self._on_battery_ui)
        self.signals.voltage_updated.connect(self._on_voltage_ui)
        self.signals.ambient_updated.connect(self._on_ambient_ui)
        self.signals.connect_ok.connect(self._on_connect_ok_ui)
        self.signals.connect_fail.connect(self._on_connect_fail_ui)
        self.signals.hw_disconnect.connect(self._on_hw_disconnect_ui)
        self.signals.auto_switch_gauge.connect(self._apply_gauge_mode)
        
        # Данные EV параметров
        self.latest_data = {
            "RPM": "—",
            "BATTERY": "—",
            "VOLTAGE": "—",
            "AMBIENT": "—"
        }
        self.gauge_modes = [
            {"mode": "RPM", "title": "RPM", "unit": "rpm", "max_value": 8000.0, "icon": "⚙️", "tag": "RPM"},
            {"mode": "BATTERY", "title": "BATTERY", "unit": "%", "max_value": 100.0, "icon": "🔋", "tag": "BATT"},
            {"mode": "VOLTAGE", "title": "12V BATT", "unit": "V", "max_value": 16.0, "icon": "⚡", "tag": "VOLT"},
            {"mode": "AMBIENT", "title": "AIR TEMP", "unit": "°C", "max_value": 50.0, "icon": "🌡️", "tag": "TEMP"}
        ]
        self.current_gauge_mode_idx = 0
        
        # Потоки для симуляции
        self._sim_thread: Optional[threading.Thread] = None
        self._sim_stop: threading.Event = threading.Event()
        
        # Watchdog таймер (для реального OBD)
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._watchdog_check)
        self.watchdog_timer.setInterval(2000)

        # Интерфейс
        self._init_ui()
        self._apply_dark_theme()
        self._update_mode_ui()

    def _init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 32, 40, 20)
        main_layout.setSpacing(32)

        # ---- Header ----
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignTop)
        
        title_text = "OBD-II DASHBOARD"
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setFont(QFont("Helvetica", 24, QFont.Bold))
        self.lbl_title.setStyleSheet("color: #a8e8ff; letter-spacing: 1px;") # Primary tint
        
        self.lbl_badge = QLabel("")
        self.lbl_badge.setFont(QFont("Courier New", 12, QFont.Bold))
        self.lbl_badge.setStyleSheet("margin-left: 15px;")
        
        title_layout = QHBoxLayout()
        title_layout.addWidget(self.lbl_title)
        title_layout.addWidget(self.lbl_badge)
        title_layout.addStretch()
        
        # Тумблер режимов (Mode Toggle)
        self.btn_mode = QPushButton("Mode: SIM")
        self.btn_mode.setObjectName("modeToggleBtn")
        self.btn_mode.setCursor(Qt.PointingHandCursor)
        self.btn_mode.setFixedSize(140, 40)
        self.btn_mode.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.btn_mode.clicked.connect(self._toggle_mode)
        
        # Кнопка Connect
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.setFixedSize(140, 40)
        self.btn_connect.setFont(QFont("Helvetica", 12, QFont.Bold))
        self.btn_connect.clicked.connect(self._toggle_connection)
        
        # Кнопка Safe Mode
        self.btn_safe_mode = QPushButton("Safe Mode: OFF")
        self.btn_safe_mode.setToolTip("Использовать медленное, но более надежное подключение для старых авто (fast=False)")
        self.btn_safe_mode.setCheckable(True)
        self.btn_safe_mode.setChecked(True) # Включаем по умолчанию
        self.btn_safe_mode.setCursor(Qt.PointingHandCursor)
        self.btn_safe_mode.setFixedSize(150, 40)
        self.btn_safe_mode.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.btn_safe_mode.clicked.connect(self._update_safe_mode_ui)
        self._update_safe_mode_ui() # Установим начальный стиль
        
        # Селектор портов (Port Selector)
        self.cb_ports = PortComboBox(self)
        self.cb_ports.setFixedSize(160, 40)
        self.cb_ports.setFont(QFont("Helvetica", 10))
        self.cb_ports.setCursor(Qt.PointingHandCursor)
        self.cb_ports.setToolTip("Выберите порт адаптера (для Bluetooth выберите Исходящий/Outgoing порт) или Auto Connect")
        self._refresh_ports()
        
        header_layout.addLayout(title_layout)
        header_layout.addWidget(self.cb_ports)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.btn_safe_mode)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.btn_mode)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.btn_connect)
        main_layout.addLayout(header_layout)

        # ---- Cards (Gauges) ----
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)
        
        # Speed Card
        self.frame_speed, self.gauge_speed, _, _ = self._create_card("SPEED", "km/h", max_value=220.0, icon="⏱️", tag="SPD")
        cards_layout.addWidget(self.frame_speed)
        
        # RPM Card (Dynamic)
        self.frame_rpm, self.gauge_rpm, self.lbl_rpm_icon, self.lbl_rpm_tag = self._create_card("RPM", "rpm", max_value=8000.0, icon="⚙️", tag="RPM")
        self.gauge_rpm.clicked.connect(self._cycle_gauge_mode)
        self.gauge_rpm.setToolTip("Click to change parameter (RPM/BATTERY/VOLTAGE/TEMP)")
        cards_layout.addWidget(self.frame_rpm)
        
        main_layout.addLayout(cards_layout, 1) # stretch factor 1
        
        # ---- Status Bar ----
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignBottom)
        
        self.lbl_status = QLabel("● Not Connected")
        self.lbl_status.setFont(QFont("Courier New", 10, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #ff1744;")
        
        self.lbl_info = QLabel("Port: None")
        self.lbl_info.setFont(QFont("Courier New", 10))
        self.lbl_info.setStyleSheet("color: #888899;")
        
        # Dummy Links (Connection Log, DTC Codes, Settings)
        links_layout = QHBoxLayout()
        links_layout.setSpacing(20)
        for text in ["Connection Log", "DTC Codes", "Settings"]:
            lbl = QLabel(text)
            lbl.setFont(QFont("Courier New", 10))
            lbl.setStyleSheet("color: #859398; font-weight: bold;")
            links_layout.addWidget(lbl)
            
        status_layout.addWidget(self.lbl_status)
        status_layout.addSpacing(15)
        status_layout.addWidget(self.lbl_info)
        status_layout.addStretch()
        status_layout.addLayout(links_layout)
        
        main_layout.addLayout(status_layout)

    def _cycle_gauge_mode(self):
        self.current_gauge_mode_idx = (self.current_gauge_mode_idx + 1) % len(self.gauge_modes)
        self._apply_gauge_mode()

    def _apply_gauge_mode(self, mode_idx=None):
        if mode_idx is not None:
            self.current_gauge_mode_idx = mode_idx
        mode_info = self.gauge_modes[self.current_gauge_mode_idx]
        
        self.lbl_rpm_icon.setText(mode_info["icon"])
        self.lbl_rpm_tag.setText(mode_info["tag"])
        self.gauge_rpm.configure(mode_info["title"], mode_info["unit"], mode_info["max_value"])
        
        mode_key = mode_info["mode"]
        self.gauge_rpm.set_value(self.latest_data[mode_key])

    def _create_card(self, title, unit, max_value, icon, tag):
        frame = QFrame()
        frame.setObjectName("cardFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        
        top_layout = QHBoxLayout()
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("color: #e3e0f7; font-size: 20px;")
        
        lbl_tag = QLabel(tag)
        lbl_tag.setFont(QFont("Courier New", 10, QFont.Bold))
        lbl_tag.setStyleSheet("""
            color: #bbc9cf;
            background-color: rgba(255, 255, 255, 0.05);
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        """)
        
        top_layout.addWidget(lbl_icon)
        top_layout.addStretch()
        top_layout.addWidget(lbl_tag)
        
        gauge = CircularGauge(title, unit, max_value)
        
        layout.addLayout(top_layout)
        layout.addWidget(gauge, 1)
        
        return frame, gauge, lbl_icon, lbl_tag

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget {
                background-color: #0F0F1A;
            }
            #cardFrame {
                background-color: #1E1E2E;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 16px;
            }
            QPushButton {
                background-color: rgba(124, 77, 255, 0.1);
                border: 1.5px solid #7c4dff;
                color: #cdbdff;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(124, 77, 255, 0.3);
            }
            QPushButton:disabled {
                background-color: #1e1e2e;
                border: 1.5px solid #333344;
                color: #4f4f5c;
            }
            QPushButton#modeToggleBtn {
                /* Будет переопределено в _update_mode_ui */
            }
            QComboBox {
                background-color: rgba(124, 77, 255, 0.05);
                border: 1.5px solid rgba(124, 77, 255, 0.4);
                color: #cdbdff;
                border-radius: 8px;
                padding-left: 12px;
                padding-right: 30px;
            }
            QComboBox:hover {
                border: 1.5px solid #7c4dff;
                background-color: rgba(124, 77, 255, 0.15);
            }
            QComboBox:disabled {
                background-color: #12121A;
                border: 1.5px solid #333344;
                color: #4f4f5c;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left: 1px solid rgba(124, 77, 255, 0.2);
            }
            QComboBox::down-arrow {
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNjZGJkZmYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #12121A;
                color: #cdbdff;
                selection-background-color: #7c4dff;
                selection-color: #ffffff;
                border: 1.5px solid rgba(124, 77, 255, 0.5);
                outline: 0px;
            }
        """)

    def _update_safe_mode_ui(self):
        if self.btn_safe_mode.isChecked():
            self.btn_safe_mode.setText("Safe Mode: ON")
            self.btn_safe_mode.setStyleSheet("""
                background-color: rgba(0, 229, 255, 0.1);
                border: 1.5px solid #00e5ff;
                color: #00e5ff;
                border-radius: 8px;
            """)
        else:
            self.btn_safe_mode.setText("Safe Mode: OFF")
            self.btn_safe_mode.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.03);
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                color: #859398;
                border-radius: 8px;
            """)

    def _toggle_mode(self):
        if self._connected or self._connecting:
            # Блокируем смену режима, пока активно подключение
            return
            
        self.simulation_mode = not self.simulation_mode
        self._update_mode_ui()

    def _update_mode_ui(self):
        if self.simulation_mode:
            self.btn_mode.setText("Mode: SIM")
            self.btn_mode.setStyleSheet("""
                background-color: rgba(0, 230, 118, 0.1);
                border: 1.5px solid #00e676;
                color: #00e676;
                border-radius: 8px;
            """)
            self.lbl_badge.setText("● [SIMULATION]")
            self.lbl_badge.setStyleSheet("color: #00e676; margin-left: 15px;")
        else:
            self.btn_mode.setText("Mode: LIVE")
            self.btn_mode.setStyleSheet("""
                background-color: rgba(255, 23, 68, 0.1);
                border: 1.5px solid #ff1744;
                color: #ff1744;
                border-radius: 8px;
            """)
            self.lbl_badge.setText("● [OFFLINE]")
            self.lbl_badge.setStyleSheet("color: #ff1744; margin-left: 15px;")

    def _refresh_ports(self):
        """
        Сканирует доступные последовательные/COM-порты в системе и
        заполняет ими выпадающий список.
        """
        # Сохраняем выбранный порт, чтобы вернуть его после обновления
        current_text = self.cb_ports.currentText() if hasattr(self, 'cb_ports') and self.cb_ports else ""
        
        self.cb_ports.clear()
        self.cb_ports.addItem("Auto Connect")
        
        if not OBD_AVAILABLE:
            return
            
        try:
            ports = obd.scan_serial()
            for p in ports:
                self.cb_ports.addItem(p)
            
            # Восстанавливаем выбранное значение
            if current_text:
                index = self.cb_ports.findText(current_text)
                if index >= 0:
                    self.cb_ports.setCurrentIndex(index)
                    
            logger.info("Обновлен список портов в GUI: %s", ports)
        except Exception as e:
            logger.error("Ошибка сканирования портов: %s", e)

    # ------------------------------------------------------------------
    #  Управление подключением
    # ------------------------------------------------------------------
    def _toggle_connection(self):
        if self._connecting:
            logger.info("Пользователь отменил подключение в процессе. Ожидание завершения потока...")
            self._connect_attempt_id += 1
            
            # Блокируем кнопку подключения на время корректного завершения потока
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Cancelling...")
            self.lbl_info.setText("Остановка процессов... Пожалуйста, подождите.")
            
            # Опрос таймером завершения потока
            self._cleanup_timer = QTimer(self)
            self._cleanup_timer.timeout.connect(self._check_thread_exited)
            self._cleanup_timer.start(200)
            return
            
        if self._connected:
            logger.info("Пользователь инициировал отключение.")
            self._disconnect()
        else:
            logger.info("Пользователь инициировал подключение. Режим симуляции: %s", self.simulation_mode)
            self._connecting = True
            self._connect_attempt_id += 1
            
            self._selected_port = self.cb_ports.currentText()
            self.cb_ports.setEnabled(False)
            
            self._use_fast_connection = not self.btn_safe_mode.isChecked()
            self.btn_safe_mode.setEnabled(False)
            
            self.btn_connect.setText("Cancel")
            self.btn_connect.setEnabled(True)
            self.btn_connect.setStyleSheet("""
                background-color: rgba(255, 171, 0, 0.1);
                border: 1.5px solid #ffab00;
                color: #ffab00;
                border-radius: 8px;
            """)
            self.btn_mode.setEnabled(False) # Блокируем тумблер во время подключения
            
            self.lbl_info.setText("Поиск ELM327 адаптера...")
            self.lbl_status.setText("● Connecting...")
            self.lbl_status.setStyleSheet("color: #ffab00;")
            
            self.lbl_badge.setText("● [CONNECTING]")
            self.lbl_badge.setStyleSheet("color: #ffab00; margin-left: 15px;")

            target = self._connect_simulation if self.simulation_mode else self._connect_real
            self._connect_thread = threading.Thread(target=target, daemon=True)
            self._connect_thread.start()

    def _check_thread_exited(self):
        """
        Проверяет по таймеру, завершился ли фоновый поток подключения.
        Как только поток умирает, завершает сброс UI в дефолтное состояние.
        """
        if not hasattr(self, '_connect_thread') or not self._connect_thread.is_alive():
            if hasattr(self, '_cleanup_timer') and self._cleanup_timer:
                self._cleanup_timer.stop()
                self._cleanup_timer = None
            logger.info("Фоновый поток подключения успешно завершен. Возврат UI в исходное состояние.")
            self._on_connect_fail_ui("CANCELLED")

    # ---- Реальный режим (выполняется в фоне!) ----
    def _connect_real(self):
        """
        Основной метод подключения к ELM327 адаптеру в реальном режиме.
        Выполняется в отдельном потоке (daemon), чтобы не "вешать" интерфейс.
        Алгоритм:
        1. Сканирует порты.
        2. Перебирает порты и скорости (baudrate). На Windows обходит баг OSError(22).
        3. Если адаптер найден, проверяет поддерживаемые команды (PIDs).
        4. Подписывается на нужные датчики (SPEED, RPM, BATTERY и т.д.).
        5. Запускает асинхронный цикл опроса (conn.start()).
        """
        current_attempt = self._connect_attempt_id
        is_fast = getattr(self, '_use_fast_connection', True)
        timeout_val = 3 if is_fast else 10
        
        def is_cancelled():
            return self._connect_attempt_id != current_attempt

        if not OBD_AVAILABLE:
            time.sleep(0.5)
            self.signals.connect_fail.emit("Библиотека python-obd не найдена!")
            return

        selected_port = getattr(self, '_selected_port', 'Auto Connect')
        logger.info("Запуск реального подключения obd.Async... Выбранный порт: %s", selected_port)
        try:
            conn = None
            found_port = None
            found_baud = None
            
            if selected_port != "Auto Connect":
                logger.info("Подключаемся напрямую к выбранному порту: %s", selected_port)
                found_port = selected_port
                found_baud = None # Позволяем python-obd автоматически подобрать скорость на конкретном порту
            else:
                # Получаем список всех доступных портов
                ports = obd.scan_serial()
                logger.info("Найдены порты для проверки: %s", ports)
                
                # ЭТАП 1: Быстрый поиск правильного порта (Fast Probe)
                # Чтобы не зависать на "мертвых" COM-портах по несколько минут (из-за Safe Mode timeout=10),
                # мы пробегаемся по всем портам с умеренным таймаутом (3.0 секунды, чтобы дать время Bluetooth-стеку).
                for port in ports:
                    if is_cancelled(): return
                    logger.info("Быстрый опрос порта: %s", port)
                    
                    for baud in [38400, 9600, 115200]:
                        if is_cancelled(): return
                        try:
                            # Пробное базовое подключение, чтобы узнать, ответит ли ELM327
                            probe = obd.OBD(portstr=port, baudrate=baud, fast=True, timeout=3.0)
                            status = probe.status()
                            probe.close()
                            
                            if status != OBDStatus.NOT_CONNECTED:
                                logger.info("✅ Адаптер откликнулся на порту %s (baudrate %s)", port, baud)
                                found_port = port
                                found_baud = baud
                                break
                        except Exception as e:
                            logger.debug("Ошибка probe на %s (%s): %s", port, baud, e)
                    
                    if found_port:
                        break

            if is_cancelled(): return

            # ЭТАП 2: Полноценное подключение Async (уже с учетом Safe Mode timeout)
            if found_port:
                logger.info("Устанавливаем главное Async соединение на %s (baudrate: %s)...", found_port, found_baud)
                try:
                    conn = obd.Async(portstr=found_port, baudrate=found_baud, fast=is_fast, timeout=timeout_val, delay_cmds=0.25)
                except Exception as e:
                    logger.error("Ошибка при создании Async: %s", e)
            elif selected_port == "Auto Connect":
                # Если перебор не сработал (или список был пуст), пробуем стандартный fallback
                logger.info("Автоматический перебор не нашел адаптер. Пробуем стандартный fallback...")
                try:
                    conn = obd.Async(fast=is_fast, timeout=timeout_val, delay_cmds=0.25)
                except Exception as e:
                    logger.warning("Стандартный obd.Async() не подключился: %s", e)
                    conn = None

            if is_cancelled():
                if conn:
                    try: conn.close()
                    except Exception: pass
                return

            # Если conn всё ещё None — ни один порт не подошёл
            if conn is None:
                logger.warning("Ни один порт не дал подключения. Адаптер не найден.")
                if selected_port != "Auto Connect":
                    self.signals.connect_fail.emit(f"Не удалось подключиться к порту {selected_port}. Убедитесь, что зажигание включено и порт выбран верно.")
                else:
                    self.signals.connect_fail.emit("Адаптер не найден. Попробуйте выбрать порт вручную из выпадающего списка.")
                return

            status = conn.status()
            logger.info("Статус подключения obd: %s", status)

            if status == OBDStatus.NOT_CONNECTED:
                logger.warning("Адаптер ELM327 не найден.")
                try: conn.close()
                except Exception: pass
                if selected_port != "Auto Connect":
                    self.signals.connect_fail.emit(f"Не удалось подключиться к {selected_port}. Убедитесь, что зажигание включено.")
                else:
                    self.signals.connect_fail.emit("Адаптер не найден. Проверьте USB/Bluetooth или выберите порт вручную.")
                return

            if is_cancelled():
                try: conn.close()
                except Exception: pass
                return

            # Логируем поддерживаемые команды для отладки
            supported = [str(c) for c in conn.supported_commands]
            logger.info("Поддерживаемые команды ECU: %s", supported)
            
            logger.info("Подписка на команды...")
            
            if obd.commands.SPEED in conn.supported_commands:
                conn.watch(obd.commands.SPEED, callback=self._on_speed_bg)
            else:
                logger.warning("SPEED не поддерживается ECU!")
            
            if obd.commands.RPM in conn.supported_commands:
                conn.watch(obd.commands.RPM, callback=self._on_rpm_bg)
            else:
                logger.info("RPM не поддерживается (EV?). Авто-переключение шкалы...")
                self.signals.auto_switch_gauge.emit(1) # Переключить на BATTERY
            
            if obd.commands.HYBRID_BATTERY_REMAINING in conn.supported_commands:
                conn.watch(obd.commands.HYBRID_BATTERY_REMAINING, callback=self._on_battery_bg)
                logger.info("Подписка на HYBRID_BATTERY_REMAINING — OK")
                
            if obd.commands.CONTROL_MODULE_VOLTAGE in conn.supported_commands:
                conn.watch(obd.commands.CONTROL_MODULE_VOLTAGE, callback=self._on_voltage_bg)
                logger.info("Подписка на CONTROL_MODULE_VOLTAGE — OK")
                
            # Учитываем опечатку в самой библиотеке python-obd (AMBIANT вместо AMBIENT)
            cmd_ambient = getattr(obd.commands, "AMBIANT_AIR_TEMP", getattr(obd.commands, "AMBIENT_AIR_TEMP", None))
            if cmd_ambient and cmd_ambient in conn.supported_commands:
                conn.watch(cmd_ambient, callback=self._on_ambient_bg)
                logger.info("Подписка на AMBIENT_AIR_TEMP — OK")

            conn.start()

            self.connection = conn
            port_name = "Unknown"
            try:
                port_name = str(conn.port_name())
            except Exception:
                pass
            logger.info("Успешное подключение. Порт: %s", port_name)
            self.signals.connect_ok.emit(str(status), port_name)

        except Exception as exc:
            logger.error("Критическая ошибка при попытке подключения: %s", exc, exc_info=True)
            self.signals.connect_fail.emit(str(exc))

    # ---- Режим симуляции (выполняется в фоне!) ----
    def _connect_simulation(self):
        """
        Метод запуска режима симуляции. 
        Запускает отдельный поток (_simulation_loop), который генерирует 
        случайные, но реалистичные значения для всех датчиков.
        """
        current_attempt = self._connect_attempt_id
        def is_cancelled():
            return self._connect_attempt_id != current_attempt

        time.sleep(0.5)
        if is_cancelled():
            return
        self._sim_stop.clear()
        self.signals.connect_ok.emit("SIMULATION", "SIMULATED")

        self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._sim_thread.start()

    def _simulation_loop(self):
        speed, rpm = 0.0, 800.0
        battery = 85.0
        voltage = 14.1
        ambient = 22.0
        while not self._sim_stop.is_set():
            speed = max(0.0, min(220.0, speed + random.uniform(-5.0, 5.0)))
            rpm = max(700.0, min(7000.0, 700 + (speed / 220.0) * 5000 + random.uniform(-200, 200)))
            battery = max(0.0, battery - random.uniform(0.0, 0.05))
            voltage = max(11.0, min(15.0, voltage + random.uniform(-0.1, 0.1)))
            ambient = ambient + random.uniform(-0.1, 0.1)
            
            self.signals.speed_updated.emit(str(int(speed)))
            self.signals.rpm_updated.emit(str(int(rpm)))
            self.signals.battery_updated.emit(str(int(battery)))
            self.signals.voltage_updated.emit(str(round(voltage, 1)))
            self.signals.ambient_updated.emit(str(int(ambient)))
            
            self._sim_stop.wait(timeout=0.2)

    # ---- Отключение ----
    def _disconnect(self):
        """
        Безопасное отключение адаптера или режима симуляции.
        Останавливает все фоновые потоки, закрывает COM-порт и
        возвращает графический интерфейс в исходное состояние "Not Connected".
        """
        logger.info("Остановка процессов и отключение...")
        self._sim_stop.set()
        if self._sim_thread:
            self._sim_thread.join(timeout=2.0)
            self._sim_thread = None

        if self.connection:
            logger.info("Остановка фонового потока obd.Async и закрытие порта...")
            conn = self.connection
            def _close():
                try: conn.stop()
                except Exception as exc: logger.error("Ошибка остановки conn.stop(): %s", exc)
                try: conn.close()
                except Exception as exc: logger.error("Ошибка закрытия conn.close(): %s", exc)
            threading.Thread(target=_close, daemon=True).start()
            self.connection = None

        self.watchdog_timer.stop()
        self._connected = False
        self._connecting = False

        # Сброс UI
        self.btn_connect.setText("Connect")
        self.btn_connect.setEnabled(True)
        self.btn_connect.setStyleSheet("") # Возврат к стандарту из CSS
        
        self.btn_mode.setEnabled(True) # Разблокируем тумблер
        self.btn_safe_mode.setEnabled(True) # Разблокируем чекбокс
        self.cb_ports.setEnabled(True) # Разблокируем селектор портов
        
        self.lbl_status.setText("● Not Connected")
        self.lbl_status.setStyleSheet("color: #ff1744;")
        self.lbl_info.setText("Отключено. Нажмите «Connect»")
        
        self._update_mode_ui() # Восстановим правильный бэйджик
        
        self.latest_data = {"RPM": "—", "BATTERY": "—", "VOLTAGE": "—", "AMBIENT": "—"}
        self.gauge_speed.set_value("—")
        self.gauge_rpm.set_value("—")

    # ------------------------------------------------------------------
    #  Коллбеки python-obd (выполняются в фоновом потоке!)
    #  Только эмитим сигналы.
    # ------------------------------------------------------------------
    def _on_speed_bg(self, response):
        try:
            if response.is_null() or response.value is None:
                self.signals.speed_updated.emit("—")
            else:
                self.signals.speed_updated.emit(str(int(response.value.to("kph").magnitude)))
        except Exception as exc:
            logger.error("Ошибка при обработке значения скорости: %s", exc, exc_info=True)
            self.signals.speed_updated.emit("ERR")

    def _on_rpm_bg(self, response):
        try:
            if response.is_null() or response.value is None:
                self.signals.rpm_updated.emit("—")
            else:
                self.signals.rpm_updated.emit(str(int(response.value.to("rpm").magnitude)))
        except Exception as exc:
            logger.error("Ошибка при обработке значения оборотов (RPM): %s", exc, exc_info=True)
            self.signals.rpm_updated.emit("ERR")

    def _on_battery_bg(self, response):
        try:
            if not response.is_null() and response.value is not None:
                val = str(int(response.value.magnitude))
                self.signals.battery_updated.emit(val)
        except Exception as exc:
            logger.error("Ошибка при обработке BATTERY: %s", exc, exc_info=True)

    def _on_voltage_bg(self, response):
        try:
            if not response.is_null() and response.value is not None:
                val = str(round(response.value.magnitude, 1))
                self.signals.voltage_updated.emit(val)
        except Exception as exc:
            logger.error("Ошибка при обработке VOLTAGE: %s", exc, exc_info=True)

    def _on_ambient_bg(self, response):
        try:
            if not response.is_null() and response.value is not None:
                val = str(int(response.value.magnitude))
                self.signals.ambient_updated.emit(val)
        except Exception as exc:
            logger.error("Ошибка при обработке AMBIENT_TEMP: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    #  Слоты UI (выполняются в главном потоке GUI!)
    # ------------------------------------------------------------------
    def _on_speed_ui(self, value: str):
        self.gauge_speed.set_value(value)

    def _on_rpm_ui(self, value: str):
        self.latest_data["RPM"] = value
        if self.gauge_modes[self.current_gauge_mode_idx]["mode"] == "RPM":
            self.gauge_rpm.set_value(value)

    def _on_battery_ui(self, value: str):
        self.latest_data["BATTERY"] = value
        if self.gauge_modes[self.current_gauge_mode_idx]["mode"] == "BATTERY":
            self.gauge_rpm.set_value(value)

    def _on_voltage_ui(self, value: str):
        self.latest_data["VOLTAGE"] = value
        if self.gauge_modes[self.current_gauge_mode_idx]["mode"] == "VOLTAGE":
            self.gauge_rpm.set_value(value)

    def _on_ambient_ui(self, value: str):
        self.latest_data["AMBIENT"] = value
        if self.gauge_modes[self.current_gauge_mode_idx]["mode"] == "AMBIENT":
            self.gauge_rpm.set_value(value)

    def _on_connect_ok_ui(self, status: str, port: str):
        self._connecting = False
        self._connected = True
        
        self.btn_connect.setText("Disconnect")
        self.btn_connect.setEnabled(True)
        self.btn_connect.setStyleSheet("""
            background-color: rgba(255, 23, 68, 0.1);
            border: 1.5px solid #ff1744;
            color: #ff1744;
            border-radius: 8px;
        """)
        
        if self.simulation_mode:
            self.lbl_status.setText("● Simulation Active")
            self.lbl_status.setStyleSheet("color: #00e676;")
            self.lbl_info.setText("Режим симуляции (случайные данные)")
            
            self.lbl_badge.setText("● [SIM]")
            self.lbl_badge.setStyleSheet("color: #00e676; margin-left: 15px;")
        else:
            self.lbl_status.setText(f"● {status}")
            if "car connected" in status.lower() or "car_connected" in status.lower():
                self.lbl_status.setStyleSheet("color: #00e676;")
                self.lbl_info.setText(f"Port: {port}")
                
                self.lbl_badge.setText("● [LIVE]")
                self.lbl_badge.setStyleSheet("color: #00e676; margin-left: 15px;")
            else:
                self.lbl_status.setStyleSheet("color: #ffab00;")
                self.lbl_info.setText("Подключено, но зажигание выключено?")
            
            self.watchdog_timer.start()

    def _on_connect_fail_ui(self, error_msg: str):
        self._connecting = False
        self.btn_connect.setText("Connect")
        self.btn_connect.setEnabled(True)
        self.btn_connect.setStyleSheet("")
        
        self.btn_mode.setEnabled(True) # Разблокируем тумблер
        self.btn_safe_mode.setEnabled(True) # Разблокируем чекбокс
        self.cb_ports.setEnabled(True) # Разблокируем селектор портов
        
        if error_msg == "CANCELLED":
            self.lbl_status.setText("● Not Connected")
            self.lbl_status.setStyleSheet("color: #ff1744;")
            self.lbl_info.setText("Подключение отменено пользователем.")
            self._update_mode_ui()
        else:
            self.lbl_status.setText("● Connection Failed")
            self.lbl_status.setStyleSheet("color: #ff1744;")
            self.lbl_info.setText(f"Ошибка: {error_msg}")
            self._update_mode_ui()

    def _on_hw_disconnect_ui(self, msg: str):
        logger.warning("Аппаратный обрыв связи: %s", msg)
        self._disconnect()
        self.lbl_info.setText(f"Обрыв связи: {msg}")

    def _watchdog_check(self):
        """
        Проверка статуса подключения по таймеру (главный поток).
        Таймер срабатывает каждые 2 секунды. 
        Если фоновый поток библиотеки python-obd остановился из-за ошибки (например, выдернули провод),
        этот метод отловит проблему и безопасно завершит сессию, уведомив пользователя об обрыве.
        """
        if self.simulation_mode or not self._connected:
            return
        try:
            if self.connection and not self.connection.running:
                logger.error("Watchdog: обнаружена остановка фонового потока obd.Async")
                self._on_hw_disconnect_ui("Поток Async остановился")
            elif self.connection and self.connection.running and OBD_AVAILABLE:
                # Дополнительный надежный опрос напряжения ELM327 (для 12V АКБ)
                try:
                    volts_response = self.connection.query(obd.commands.ELM_VOLTAGE)
                    if not volts_response.is_null() and volts_response.value is not None:
                        val = str(round(volts_response.value.magnitude, 1))
                        # Если нет других данных о вольтаже, используем ELM_VOLTAGE
                        if self.latest_data.get("VOLTAGE") == "—":
                            self.signals.voltage_updated.emit(val)
                except Exception as e:
                    logger.debug("Watchdog: не удалось запросить ELM_VOLTAGE: %s", e)
        except Exception as exc:
            logger.error("Watchdog: ошибка при проверке состояния соединения: %s", exc, exc_info=True)
            self._on_hw_disconnect_ui("Адаптер недоступен")

    def closeEvent(self, event):
        """Вызывается при закрытии окна (крестик)."""
        self._disconnect()
        event.accept()

# ---------------------------------------------------------------------------
#  Точка входа
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    
    # Делаем стиль более современным перед применением Dark Theme
    app.setStyle("Fusion")
    
    window = OBDApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
