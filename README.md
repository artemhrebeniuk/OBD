# Панель приборов OBD-II Dashboard

Кроссплатформенное десктопное приложение (Windows / macOS) для визуализации параметров автомобиля в реальном времени через диагностический интерфейс OBD-II (ELM327).

> [!NOTE]
> Данный файл служит основным руководством для ИИ-ассистентов (LLM) и разработчиков. Он описывает архитектуру, ключевые фичи, особенности работы с аппаратным обеспечением и процесс сборки приложения.

---

## 📋 Описание проекта

Приложение подключается к адаптеру ELM327 (USB или Bluetooth) и считывает данные о скорости автомобиля, оборотах двигателя, заряде гибридной/электрической батареи, напряжении бортовой сети и температуре окружающего воздуха.

Интерфейс спроектирован в стиле **"Cyber-Drive"** (темная неоновая тема) с использованием двух больших круговых шкал (Gauges):
1. **Левая шкала**: Скорость (км/ч) — постоянный параметр.
2. **Правая шкала**: Динамический параметр. По умолчанию отображает RPM (обороты двигателя), но пользователь может переключать её кликом мыши (RPM ➡️ Заряд батареи (%) ➡️ Вольтаж сети (В) ➡️ Температура воздуха (°C)).

---

## ⚡ Ключевые возможности и особенности

1. **Режимы LIVE и SIM (Симуляция)**:
   - **LIVE**: Полноценное подключение к ELM327. Автоматически сканирует доступные COM-порты и опрашивает ЭБУ автомобиля в асинхронном режиме.
   - **SIM**: Демонстрационный режим. Генерирует случайные реалистичные изменения показателей без необходимости физического подключения к OBD-II адаптеру.
2. **Адаптация под электромобили (EV/Hybrid)**:
   - Приложение автоматически проверяет поддержку PID-кода оборотов двигателя (`RPM`). Если машина электрическая (например, Audi e-tron), то RPM не поддерживается.
   - В таком случае приложение автоматически скрывает RPM и переключает правую шкалу на параметры батареи/температуры (`BATTERY` / `VOLTAGE` / `AMBIENT`).
3. **Обход критической ошибки Bluetooth на Windows (OSError 22)**:
   - Стандартный метод `obd.Async()` в библиотеке `python-obd` использует автоматический подбор скорости (baudrate auto-detection). На Windows виртуальные COM-порты Bluetooth падают с ошибкой `OSError(22)` при частой смене baudrate.
   - **Решение в коде**: Мы реализовали кастомный перебор портов с явным указанием скорости: сначала пробуем стабильный `38400` (стандарт для Bluetooth ELM327), затем `9600` (для старых USB-кабелей), и только потом авто-подбор. Все попытки обернуты в блоки перехвата исключений, что гарантирует стабильность и отсутствие падений программы.
4. **Контроль обрыва связи (Watchdog)**:
   - Таймер каждые 2 секунды проверяет состояние фонового потока опроса. Если поток завис или отключился, приложение безопасно сбрасывает соединение и выводит уведомление пользователю, не давая зависнуть графическому интерфейсу.
5. **Ротируемое логирование**:
   - Логи пишутся в файл `obd_dashboard.log` рядом с исполняемым файлом (как `.py`, так и собранным `.exe`).
   - Файл логирования ограничен размером в 5 МБ с автоматической ротацией (сохраняется один бэкап-файл `obd_dashboard.log.1`). Шумные предупреждения сторонних библиотек (`pint` и `obd`) отключаются.

---

## 🛠 Технологический стек

- **Python 3.9+**
- **PyQt5** (Fusion-стиль графического интерфейса) — обеспечивает аппаратное ускорение и одинаковый вид на всех ОС.
- **python-obd** (асинхронный клиент `obd.Async`) — для работы с ELM327.
- **Pint** — для безопасной конвертации физических величин.
- **PyInstaller** — для сборки в один EXE-файл без внешних зависимостей.

---

## 📂 Структура проекта и файлы

- [main.py](file:///Users/mr_shpepe/Documents/OBD_CHECK/main.py) — весь исходный код приложения (интерфейс PyQt5, логика соединения, потоки опроса).
- [requirements.txt](file:///Users/mr_shpepe/Documents/OBD_CHECK/requirements.txt) — список библиотек-зависимостей.
- [DESIGN.md](file:///Users/mr_shpepe/Documents/OBD_CHECK/DESIGN.md) — требования к дизайну и UI/UX.
- `obd_dashboard.log` — файл с актуальными логами работы приложения.

---

## 🤖 Руководство для ИИ-ассистентов (LLM Context)

При работе с кодом приложения учитывайте следующие архитектурные решения:

### 1. Потокобезопасность (GUI и фоновые процессы)
Потоки графического интерфейса (PyQt5) и фоновые потоки опроса OBD разделены. Фоновые коллбеки `python-obd` (такие как `_on_speed_bg`, `_on_rpm_bg`) **не должны напрямую изменять элементы GUI**.
Для связи используются Qt-сигналы через вспомогательный класс `UISignals` (объект `self.signals` в `OBDApp`):
- Фоновый поток испускает сигнал (например, `self.signals.speed_updated.emit("50")`).
- GUI-поток ловит сигнал в слоте (например, `_on_speed_ui`) и безопасно обновляет виджеты.

### 2. Алгоритм подключения в `main.py`
Метод подключения `_connect_real` выполняется в отдельном Python-потоке (`threading.Thread`), чтобы не замораживать интерфейс во время сканирования портов:
1. Вызывается `obd.scan_serial()`.
2. В цикле перебираются порты. На каждом порту пробуются скорости `38400`, `9600` и `auto` с созданием `obd.Async(...)`.
3. При успешном статусе (`status() != OBDStatus.NOT_CONNECTED`), соединение сохраняется.
4. Проверяется список поддерживаемых PIDs (`conn.supported_commands`). Оформляется подписка (`conn.watch(...)`) на доступные датчики.
5. Запускается цикл опроса: `conn.start()`.
6. Оповещается GUI через `self.signals.connect_ok`.

### 3. Сборка исполняемого файла (EXE)
Сборка проекта под Windows или macOS производится с помощью `pyinstaller`.
Команда для консоли:
```bash
pyinstaller --noconsole --onefile --clean --name "OBD_Dashboard" main.py
```
*Примечание:* Для сборки под Windows команду нужно выполнять непосредственно на ОС Windows.

---

## 📖 Полная документация библиотеки python-obd (для справки)

Ниже представлена оригинальная документация библиотеки `python-obd`, описывающая работу классов `OBD`, `Async`, получение ответов `OBDResponse` и работу с физическими величинами `Pint`.

---


# Welcome

Python-OBD is a library for handling data from a car's [**O**n-**B**oard **D**iagnostics](https://en.wikipedia.org/wiki/On-board_diagnostics) port. Please keep in mind that the car **must** have OBD-II (any car made in 1996 and up); this will _**not**_ work with OBD-I.

Python-OBD can stream real time sensor data, perform diagnostics (such as reading check-engine codes), and is fit for the Raspberry Pi. This library is designed to work with standard [ELM327 OBD-II adapters](http://www.amazon.com/s/ref=nb_sb_noss?field-keywords=elm327).

<span style="color:red">*NOTE: Python-OBD is below 1.0.0, meaning the API may change between minor versions. Consult the [GitHub release page](https://github.com/brendan-w/python-OBD/releases) for changelogs before updating.*</span>

<br>

## Installation

Install the latest release from pypi:

```shell
$ pip install obd
```

*Note: If you are using a Bluetooth adapter on Linux, you may also need to install and configure your Bluetooth stack. On Debian-based systems, this usually means installing the following packages:*

```shell
$ sudo apt-get install bluetooth bluez-utils blueman
```

<br>

## Basic Usage

```python
import obd

connection = obd.OBD() # auto-connects to USB or RF port

cmd = obd.commands.SPEED # select an OBD command (sensor)

response = connection.query(cmd) # send the command and parse the response

print(response.value) # returns unit-bearing values thanks to Pint
print(response.value.to("mph")) # user-friendly unit conversions
```

OBD connections operate in a request-reply fashion. To retrieve data from the car, you must send commands that query for the data you want (e.g. RPM, Vehicle speed, etc). In python-OBD this is done with the `query()` function. The commands themselves are represented as objects and can be looked up by name or value in `obd.commands`. The `query()` function will return a response object with parsed data in its `value` property.

<br>

## Module Layout

```python
import obd

obd.OBD            # main OBD connection class
obd.Async          # asynchronous OBD connection class
obd.commands       # command tables
obd.Unit           # unit tables (a Pint UnitRegistry)
obd.OBDStatus      # enum for connection status
obd.scan_serial    # util function for manually scanning for OBD adapters
obd.OBDCommand     # class for making your own OBD Commands
obd.ECU            # enum for marking which ECU a command should listen to
obd.logger         # the OBD module's root logger (for debug)
```

<br>

## License

GNU General Public License V2

---

<br>


---

# README

python-OBD
==========

A python module for handling realtime sensor data from OBD-II vehicle
ports. Works with ELM327 OBD-II adapters, and is fit for the Raspberry
Pi.

Installation
------------

```Shell
$ pip install obd
```

Basic Usage
-----------

```Python
import obd

connection = obd.OBD() # auto-connects to USB or RF port

cmd = obd.commands.SPEED # select an OBD command (sensor)

response = connection.query(cmd) # send the command, and parse the response

print(response.value) # returns unit-bearing values thanks to Pint
print(response.value.to("mph")) # user-friendly unit conversions
```

Documentation
-------------

Available at [python-obd.readthedocs.org](http://python-obd.readthedocs.org/en/latest/)

Commands
--------

Here are a handful of the supported commands (sensors). For a full list, see [the docs](http://python-obd.readthedocs.io/en/latest/Command%20Tables/)

*note: support for these commands will vary from car to car*

-   Calculated Engine Load
-   Engine Coolant Temperature
-   Fuel Pressure
-   Intake Manifold Pressure
-   Engine RPM
-   Vehicle Speed
-   Timing Advance
-   Intake Air Temp
-   Air Flow Rate (MAF)
-   Throttle Position
-   Engine Run Time
-   Fuel Level Input
-   Number of warm-ups since codes cleared
-   Barometric Pressure
-   Ambient air temperature
-   Commanded throttle actuator
-   Time run with MIL on
-   Time since trouble codes cleared
-   Hybrid battery pack remaining life
-   Engine fuel rate
-   Vehicle Identification Number (VIN)

Common Issues
-------------

### Bluetooth OBD-II Adapters

There are sometimes connection issues when using a Bluetooth OBD-II adapter with some devices (the Raspberry Pi is a common problem). This can be fixed by setting the following arguments when setting up the connection:

```Python
fast=False, timeout=30
```

License
-------

GNU GPL v2

This library is forked from:

-   <https://github.com/peterh/pyobd>
-   <https://github.com/Pbartek/pyobd-pi>

Enjoy and drive safe!


---

# Connections

After installing the library, simply `import obd`, and create a new OBD connection object. By default, python-OBD will scan for Bluetooth and USB serial ports (in that order), and will pick the first connection it finds. The port can also be specified manually by passing a connection string to the OBD constructor. You can also use the `scan_serial` helper retrieve a list of connected ports.

```python
import obd

connection = obd.OBD() # auto connect

# OR

connection = obd.OBD("/dev/ttyUSB0") # create connection with USB 0

# OR

ports = obd.scan_serial()      # return list of valid USB or RF ports
print ports                    # ['/dev/ttyUSB0', '/dev/ttyUSB1']
connection = obd.OBD(ports[0]) # connect to the first port in the list
```


<br>

### OBD(portstr=None, baudrate=None, protocol=None, fast=True, timeout=0.1, check_voltage=True, start_low_power=False):

`portstr`: The UNIX device file or Windows COM Port for your adapter. The default value (`None`) will auto select a port.

`baudrate`: The baudrate at which to set the serial connection. This can vary from adapter to adapter. Typical values are: 9600, 38400, 19200, 57600, 115200. The default value (`None`) will auto select a baudrate.

`protocol`: Forces python-OBD to use the given protocol when communicating with the adapter. See [protocol_id()](#protocol_id) for possible values. The default value (`None`) will auto select a protocol.

`fast`: Allows commands to be optimized before being sent to the car. Python-OBD currently makes two such optimizations:

- Sends carriage returns to repeat the previous command.
- Appends a response limit to the end of the command, telling the adapter to return after it receives *N* responses (rather than waiting and eventually timing out). This feature can be enabled and disabled for individual commands.

Disabling fast mode will guarantee that python-OBD outputs the unaltered command for every request.

`timeout`: Specifies the connection timeout in seconds.

`check_voltage`: Optional argument that is `True` by default and when set to `False` disables the detection of the car supply voltage on OBDII port (which should be about 12V). This control assumes that, if the voltage is lower than 6V, the OBDII port is disconnected from the car. If the option is enabled, it adds the `OBDStatus.OBD_CONNECTED` status, which is set when enough voltage is returned (socket connected to the car) but the ignition is off (no communication with the vehicle). Setting the option to `False` should be needed when the adapter does not support the voltage pin or more generally when the hardware provides unreliable results, or if the pin reads the switched ignition voltage rather than the battery positive (this depends on the car).

`start_low_power`: Optional argument that defaults to `False`. If set to `True` the initial connection will take longer (roughly 1 more second) but will support waking the ELM327 from low power mode before starting the connection. It does this by sending a space to the chip to trigger a charecter being received on the RS232 input line. This is sent before the baud rate is setup, to ensure the device is awake to detect the baud rate.

<br>

---

### query(command, force=False)

Sends an `OBDCommand` to the car, and returns an `OBDResponse` object. This function will block until a response is received from the car. This function will also check whether the given command is supported by your car. If a command is not marked as supported, it will not be sent, and an empty `OBDResponse` will be returned. To force an unsupported command to be sent, there is an optional `force` parameter for your convenience.

*For non-blocking querying, see [Async Querying](Async Connections.md)*

```python
import obd
connection = obd.OBD()

r = connection.query(obd.commands.RPM) # returns the response from the car
```

---

### status()

Returns a string value reflecting the status of the connection after OBD() or Async() methods are executed. These values should be compared against the `OBDStatus` class. The fact that they are strings is for human readability only. There are currently 4 possible states:

```python
from obd import OBDStatus

# no connection is made
OBDStatus.NOT_CONNECTED # "Not Connected"

# successful communication with the ELM327 adapter
OBDStatus.ELM_CONNECTED # "ELM Connected"

# successful communication with the ELM327 adapter,
# OBD port connected to the car, ignition off
# (not available with argument "check_voltage=False")
OBDStatus.OBD_CONNECTED # "OBD Connected"

# successful communication with the ELM327 and the
# vehicle; ignition on
OBDStatus.CAR_CONNECTED # "Car Connected"
```

The status is set by `OBD()` or `Async()` methods and remains unmodified during the connection. `status()` shall not be checked after the queries to verify that the connection is kept active.

`ELM_CONNECTED` and `OBD_CONNECTED` are mostly for diagnosing errors. When a proper connection is established with the vehicle, you will never encounter these values.

The ELM327 controller allows OBD Commands and AT Commands. In general, OBD Commands (which interact with the car) can be succesfully performed when the ignition is on, while AT Commands (which generally interact with the ELM327 controller) are always accepted. As the connection phase (for both `OBD` and `Async` objects) also performs OBD protocol commands (after the initial set of AT Commands) and returns the “Car Connected” status (“CAR_CONNECTED”) if the overall connection phase is successful, this status means that the serial communication is valid, that the ELM327 adapter is appropriately responding, that the OBDII socket is connected to the car and also that the ignition is on. “OBD Connected” status (“OBD_CONNECTED”) is returned when the OBDII socket is connected and the ignition is off, while the "ELM Connected" status (“ELM_CONNECTED”) means that the ELM327 processor is reached but the OBDII socket is not connected to the car. “OBD Connected” is controlled by the `check_voltage` option that by default is set to `True` and gets the ignition status when the socket is connected. If the OBDII socket does not support the unswitched battery positive supply, or the OBDII adapter cannot detect it, then the `check_voltage` option should be set to `False`; in such case, the "ELM Connected" status is returned when the socket is not connected or when the ignition is off, with no differentiation.

---

### is_connected()

Returns a boolean for whether a connection was established with the vehicle. It is identical to writing:

```python
connection.status() == OBDStatus.CAR_CONNECTED
```

---

### port_name()

Returns the string name for the currently connected port (`"/dev/ttyUSB0"`). If no connection was made, this function returns an empty string.

---

### supports(command)

Returns a boolean for whether a command is supported by both the car and python-OBD

---

### protocol_id()
### protocol_name()

Both functions return string names for the protocol currently being used by the adapter. Protocol *ID's* are the short values used by your adapter, whereas protocol *names* are the human-readable versions. The `protocol_id()` function is a good way to lookup which value to pass in the `protocol` field of the OBD constructor (though, this is mainly for advanced usage). These functions do not make any serial requests. When no connection has been made, these functions will return empty strings. The possible values are:

|ID | Name                     |
|---|--------------------------|
| "1" | SAE J1850 PWM            |
| "2" | SAE J1850 VPW            |
| "3" | AUTO, ISO 9141-2         |
| "4" | ISO 14230-4 (KWP 5BAUD)  |
| "5" | ISO 14230-4 (KWP FAST)   |
| "6" | ISO 15765-4 (CAN 11/500) |
| "7" | ISO 15765-4 (CAN 29/500) |
| "8" | ISO 15765-4 (CAN 11/250) |
| "9" | ISO 15765-4 (CAN 29/250) |
| "A" | SAE J1939 (CAN 29/250)   |

*Note the quotations around the possible IDs*

---

<!--

### ecus()

Returns a list of identified "Engine Control Units" visible to the adapter. Each value in the list is a constant representing that ECU's function. These constants are found in the `ECU` class:

```python
from obd import ECU

ECU.UNKNOWN
ECU.ENGINE
```

Python-OBD can currently only detect the engine computer, but future versions may extend this capability.

-->

### close()

Closes the connection.

---

### supported_commands

Property containing a `set` of commands that are supported by the car.

If you wish to manually mark a command as supported (prevents having to use `query(force=True)`), add the command to this set. This is not necessary when using python-OBD's builtin commands, but is useful if you create [custom commands](Custom Commands.md).

```python
import obd
connection = obd.OBD()

# manually mark the given command as supported
connection.supported_commands.add(<OBDCommand>)
```
---

<br>


---

# Async Connections

Since the standard `query()` function is blocking, it can be a hazard for UI event loops. To deal with this, python-OBD has an `Async` connection object that can be used in place of the standard `OBD` object. `Async` is a subclass of `OBD`, and therefore inherits all of the standard methods. However, `Async` adds a few in order to control a threaded update loop. This loop will keep the values of your commands up to date with the vehicle. This way, when the user `query`s the car, the latest response is returned immediately.

The update loop is controlled by calling `start()` and `stop()`. To subscribe a command for updating, call `watch()` with your requested OBDCommand. Because the update loop is threaded, commands can only be `watch`ed while the loop is `stop`ed.

General sequence to enable an asynchronous connection allowing non-blocking queries:
- *Async()* # set-up the connection (to be used in place of *OBD()*)
- *watch()* # add commands to the watch list
- *start()* # start a thread performing the update loop in background
- *query()* # perform the non-blocking query

Example:

```python
import obd

connection = obd.Async() # same constructor as 'obd.OBD()'; see below.

connection.watch(obd.commands.RPM) # keep track of the RPM

connection.start() # start the async update loop

print connection.query(obd.commands.RPM) # non-blocking, returns immediately
```

Callbacks can also be specified in `watch()`, and will return new `Response`s when available.

```python
import obd
import time

connection = obd.Async()

# a callback that prints every new value to the console
def new_rpm(r):
    print (r.value)

connection.watch(obd.commands.RPM, callback=new_rpm)
connection.start()

# the callback will now be fired upon receipt of new values

time.sleep(60)
connection.stop()
```

<br>

---

### Async(portstr=None, baudrate=None, protocol=None, fast=True, timeout=0.1, check_voltage=True, delay_cmds=0.25)

Create asynchronous connection.
Arguments are the same as 'obd.OBD()' with the addition of *delay_cmds*, which defaults to 0.25 seconds and allows
controlling a delay after each loop executing all *watch*ed commands in background. If *delay_cmds* is set to 0,
the background thread continuously repeats the execution of all commands without any delay.

---

### start()

Starts the update loop.

---

### stop()

Stops the update loop.

---

### paused()

A helper function for use in a Context Manager (a `with` statement) to temporarily stop the update loop. This makes it easy to protect your `watch()` and `unwatch()` calls. If the update loop was running at the time of being paused, it will be restarted upon exitting the context block. For instance:

```python
with connection.paused() as was_running:
	# connection is stopped within this block
	# your code here
```

The code above is equivalent to:

```python
was_running = connection.running
connection.stop()

# your code here

if was_running:
	connection.start()
```

---

### watch(command, callback=None, force=False)

*Note: The async loop must be stopped or paused before this function can be called*

Subscribes a command to be continuously updated. After calling `watch()`, the `query()` function will return the latest `Response` from that command. An optional callback can also be set, and will be fired upon receipt of new values. Multiple callbacks for the same command are welcome. An optional `force` parameter will force an unsupported command to be sent.

---

### unwatch(command, callback=None)

*Note: The async loop must be stopped or paused before this function can be called*

Unsubscribes a command from being updated. If no callback is specified, all callbacks for that command are dropped. If a callback is given, only that callback is unsubscribed (all others remain live).

---

### unwatch_all()

*Note: The async loop must be stopped or paused before this function can be called*

Unsubscribes all commands and callbacks.

---

<br>


---

# Responses

The `query()` function returns `OBDResponse` objects. These objects have the following properties:

| Property | Description                                                            |
|----------|------------------------------------------------------------------------|
| value    | The decoded value from the car                                         |
| command  | The `OBDCommand` object that triggered this response                   |
| message  | The internal `Message` object containing the raw response from the car |
| time     | Timestamp of response (as given by [`time.time()`](https://docs.python.org/2/library/time.html#time.time)) |



---

## is_null()

Use this function to check if a response is empty. Python-OBD will emit empty responses when it is unable to retrieve data from the car.

```python
r = connection.query(obd.commands.RPM)

if not r.is_null():
	print(r.value)
```

---


## Pint Values

The `value` property typically contains a [Pint](http://pint.readthedocs.io/en/latest/) `Quantity` object, but can also hold complex structures (depending on the request). Pint quantities combine a value and unit into a single class, and are used to represent physical values such as "4 seconds", and "88 mph". This allows for consistency when doing math and unit conversions. Pint maintains a registry of units, which is exposed in python-OBD as `obd.Unit`.

Below are common operations that can be done with Pint units and quantities. For more information, check out the [Pint Documentation](http://pint.readthedocs.io/en/latest/).

<span style="color:red">*NOTE: for backwards compatibility with previous versions of python-OBD, use `response.value.magnitude` in place of `response.value`*</span>

```python
import obd

>>> response.value
<Quantity(100, 'kph')>

# get the raw python datatype
>>> response.value.magnitude
100

# converts quantities to strings
>>> str(response.value)
'100 kph'

# convert strings to quantities
>>> obd.Unit("100 kph")
<Quantity(100, 'kph')>

# handles conversions nicely
>>> response.value.to('mph')
<Quantity(62.13711922373341, 'mph')>

# scaler math
>>> response.value / 2
<Quantity(50.0, 'kph')>

# non-scaler math requires you to specify units yourself
>>> response.value + (20 * obd.Unit.kph)
<Quantity(120, 'kph')>

# non-scaler math with different units
# handles unit conversions transparently
>>> response.value + (20 * obd.Unit.mph)
<Quantity(132.18688, 'kph')>
```

---

## Status

The status command returns information about the Malfunction Indicator Light (check-engine light), the number of trouble codes being thrown, and the type of engine.

```python
response.value.MIL              # boolean for whether the check-engine is lit
response.value.DTC_count        # number (int) of DTCs being thrown
response.value.ignition_type    # "spark" or "compression"
```

The status command also provides information regarding the availability and status of various system tests. These are exposed as `StatusTest` objects, loaded into named properties. Each test object has boolean flags for its availability and completion.

```python
response.value.MISFIRE_MONITORING.available    # boolean for test availability
response.value.MISFIRE_MONITORING.complete     # boolean for test completion
```

Here are all of the tests names that python-OBD reports:

| Tests                             |
|-----------------------------------|
| MISFIRE_MONITORING                |
| FUEL_SYSTEM_MONITORING            |
| COMPONENT_MONITORING              |
| CATALYST_MONITORING               |
| HEATED_CATALYST_MONITORING        |
| EVAPORATIVE_SYSTEM_MONITORING     |
| SECONDARY_AIR_SYSTEM_MONITORING   |
| OXYGEN_SENSOR_MONITORING          |
| OXYGEN_SENSOR_HEATER_MONITORING   |
| EGR_VVT_SYSTEM_MONITORING         |
| NMHC_CATALYST_MONITORING          |
| NOX_SCR_AFTERTREATMENT_MONITORING |
| BOOST_PRESSURE_MONITORING         |
| EXHAUST_GAS_SENSOR_MONITORING     |
| PM_FILTER_MONITORING              |


---

## Diagnostic Trouble Codes (DTCs)

Each DTC is represented by a tuple containing the DTC code, and a description (if python-OBD has one). For commands that return multiple DTCs, a list is used.

```python
# obd.commands.GET_DTC
response.value = [
    ("P0104", "Mass or Volume Air Flow Circuit Intermittent"),
    ("B0003", ""), # unknown error code, it's probably vehicle-specific
    ("C0123", "")
]

# obd.commands.FREEZE_DTC
response.value = ("P0104", "Mass or Volume Air Flow Circuit Intermittent")
```

---

## Fuel Status

The fuel status is a tuple of two strings, telling the status of the first and second fuel systems. Most cars only have one system, so the second element will likely be an empty string. The possible fuel statuses are:

| Fuel Status                                                                                   |
| ----------------------------------------------------------------------------------------------|
| `""`                                                                                          |
| `"Open loop due to insufficient engine temperature"`                                          |
| `"Closed loop, using oxygen sensor feedback to determine fuel mix"`                           |
| `"Open loop due to engine load OR fuel cut due to deceleration"`                              |
| `"Open loop due to system failure"`                                                           |
| `"Closed loop, using at least one oxygen sensor but there is a fault in the feedback system"` |

---

## Air Status

The air status will be one of these strings:

| Air Status                             |
| ---------------------------------------|
| `"Upstream"`                           |
| `"Downstream of catalytic converter"`  |
| `"From the outside atmosphere or off"` |
| `"Pump commanded on for diagnostics"`  |

---

## Oxygen Sensors Present

Returns a 2D structure of tuples (representing bank and sensor number), that holds boolean values for sensor presence.

```python
# obd.commands.O2_SENSORS
response.value = (
    (),                           # bank 0 is invalid, this is merely for correct indexing
    (True,  True,  True,  False), # bank 1
    (False, False, False, False)  # bank 2
)

# obd.commands.O2_SENSORS_ALT
response.value = (
    (),             # bank 0 is invalid, this is merely for correct indexing
    (True,  True),  # bank 1
    (True,  False), # bank 2
    (False, False), # bank 3
    (False, False)  # bank 4
)

# example usage:
response.value[1][2] == True # Bank 1, Sensor 2 is present
```
---

## Monitors (Mode 06 Responses)

All mode 06 commands return `Monitor` objects holding various test results for the requested sensor. A single monitor response can hold multiple tests, in the form of `MonitorTest` objects. The OBD standard defines some tests, but vehicles can always implement custom tests beyond the standard. Here are the standard Test IDs (TIDs) that python-OBD will recognize:

| TID | Name                     | Description                                        |
|-----|--------------------------|----------------------------------------------------|
| 01  | RTL_THRESHOLD_VOLTAGE    | Rich to lean sensor threshold voltage              |
| 02  | LTR_THRESHOLD_VOLTAGE    | Lean to rich sensor threshold voltage              |
| 03  | LOW_VOLTAGE_SWITCH_TIME  | Low sensor voltage for switch time calculation     |
| 04  | HIGH_VOLTAGE_SWITCH_TIME | High sensor voltage for switch time calculation    |
| 05  | RTL_SWITCH_TIME          | Rich to lean sensor switch time                    |
| 06  | LTR_SWITCH_TIME          | Lean to rich sensor switch time                    |
| 07  | MIN_VOLTAGE              | Minimum sensor voltage for test cycle              |
| 08  | MAX_VOLTAGE              | Maximum sensor voltage for test cycle              |
| 09  | TRANSITION_TIME          | Time between sensor transitions                    |
| 0A  | SENSOR_PERIOD            | Sensor period                                      |
| 0B  | MISFIRE_AVERAGE          | Average misfire counts for last ten driving cycles |
| 0C  | MISFIRE_COUNT            | Misfire counts for last/current driving cycles     |

Test results can be accessed by property name or TID (same as the `obd.commands` tables). All of the standard tests above will be present, though some may be null. Use the `MonitorTest.is_null()` function to determine if a test is null.

```python
response.value.MISFIRE_COUNT

# OR

response.value["MISFIRE_COUNT"]

# OR

response.value[0x0C] # TID for MISFIRE_COUNT
```

All `MonitorTest` objects have the following properties: (for null tests, these are set to `None`)

```python
result = response.value.MISFIRE_COUNT

result.tid      # integer Test ID for this test
result.name     # test name
result.desc     # test description
result.value    # value of the test (will be a Pint value, or in rare cases, a boolean)
result.min      # maximum acceptable value
result.max      # minimum acceptable value
result.passed   # boolean marking the test as passing
```

Here is an example of looking up live misfire counts for the engine's second cylinder:

```python
import obd

connection = obd.OBD()

response = connection.query(obd.commands.MONITOR_MISFIRE_CYLINDER_2)

# in the test results, lookup the result for MISFIRE_COUNT
result = response.value.MISFIRE_COUNT

# check that we got data for this test
if not result.is_null():
    print(result.value) # will be a Pint value
else:
    print("Misfire count wasn't reported")
```

---

<br>


---

# Command Lookup

`OBDCommand`s are objects used to query information from the vehicle. They contain all of the information necessary to perform the query and decode the car's response. Python-OBD has [built in tables](Command Tables.md) for the most common commands. They can be looked up by name or by mode & PID.

```python
import obd

c = obd.commands.RPM

# OR

c = obd.commands['RPM']

# OR

c = obd.commands[1][12] # mode 1, PID 12 (RPM)
```

The `commands` table also has a few helper methods for determining if a particular name or PID is present.

---

### has_command(command)

Checks the internal command tables for the existance of the given `OBDCommand` object. Commands are compared by mode and PID value.

```python
import obd
obd.commands.has_command(obd.commands.RPM) # True
```

---

### has_name(name)

Checks the internal command tables for a command with the given name. This is also the function of the `in` operator.

```python
import obd

obd.commands.has_name('RPM') # True

# OR

'RPM' in obd.commands # True
```

---

### has_pid(mode, pid)

Checks the internal command tables for a command with the given mode and PID.

```python
import obd
obd.commands.has_pid(1, 12) # True
```

---

<br>


---

# Commands

## OBD-II adapter (ELM327 commands)

|PID  | Name        | Description                             | Response Value        |
|-----|-------------|-----------------------------------------|-----------------------|
| N/A | ELM_VERSION | OBD-II adapter version string           | string                |
| N/A | ELM_VOLTAGE | Voltage detected by OBD-II adapter      | Unit.volt             |

<br>

## Mode 01

|PID | Name                      | Description                             | Response Value        |
|----|---------------------------|-----------------------------------------|-----------------------|
| 00 | PIDS_A                    | Supported PIDs [01-20]                  | BitArray              |
| 01 | STATUS                    | Status since DTCs cleared               | [special](Responses.md#status) |
| 02 | FREEZE_DTC                | DTC that triggered the freeze frame     | [special](Responses.md#diagnostic-trouble-codes-dtcs) |
| 03 | FUEL_STATUS               | Fuel System Status                      | [(string, string)](Responses.md#fuel-status) |
| 04 | ENGINE_LOAD               | Calculated Engine Load                  | Unit.percent          |
| 05 | COOLANT_TEMP              | Engine Coolant Temperature              | Unit.celsius          |
| 06 | SHORT_FUEL_TRIM_1         | Short Term Fuel Trim - Bank 1           | Unit.percent          |
| 07 | LONG_FUEL_TRIM_1          | Long Term Fuel Trim - Bank 1            | Unit.percent          |
| 08 | SHORT_FUEL_TRIM_2         | Short Term Fuel Trim - Bank 2           | Unit.percent          |
| 09 | LONG_FUEL_TRIM_2          | Long Term Fuel Trim - Bank 2            | Unit.percent          |
| 0A | FUEL_PRESSURE             | Fuel Pressure                           | Unit.kilopascal       |
| 0B | INTAKE_PRESSURE           | Intake Manifold Pressure                | Unit.kilopascal       |
| 0C | RPM                       | Engine RPM                              | Unit.rpm              |
| 0D | SPEED                     | Vehicle Speed                           | Unit.kph              |
| 0E | TIMING_ADVANCE            | Timing Advance                          | Unit.degree           |
| 0F | INTAKE_TEMP               | Intake Air Temp                         | Unit.celsius          |
| 10 | MAF                       | Air Flow Rate (MAF)                     | Unit.grams_per_second |
| 11 | THROTTLE_POS              | Throttle Position                       | Unit.percent          |
| 12 | AIR_STATUS                | Secondary Air Status                    | [string](Responses.md#air-status) |
| 13 | O2_SENSORS                | O2 Sensors Present                      | [special](Responses.md#oxygen-sensors-present) |
| 14 | O2_B1S1                   | O2: Bank 1 - Sensor 1 Voltage           | Unit.volt             |
| 15 | O2_B1S2                   | O2: Bank 1 - Sensor 2 Voltage           | Unit.volt             |
| 16 | O2_B1S3                   | O2: Bank 1 - Sensor 3 Voltage           | Unit.volt             |
| 17 | O2_B1S4                   | O2: Bank 1 - Sensor 4 Voltage           | Unit.volt             |
| 18 | O2_B2S1                   | O2: Bank 2 - Sensor 1 Voltage           | Unit.volt             |
| 19 | O2_B2S2                   | O2: Bank 2 - Sensor 2 Voltage           | Unit.volt             |
| 1A | O2_B2S3                   | O2: Bank 2 - Sensor 3 Voltage           | Unit.volt             |
| 1B | O2_B2S4                   | O2: Bank 2 - Sensor 4 Voltage           | Unit.volt             |
| 1C | OBD_COMPLIANCE            | OBD Standards Compliance                | string                |
| 1D | O2_SENSORS_ALT            | O2 Sensors Present (alternate)          | [special](Responses.md#oxygen-sensors-present) |
| 1E | AUX_INPUT_STATUS          | Auxiliary input status (power take off) | boolean               |
| 1F | RUN_TIME                  | Engine Run Time                         | Unit.second           |
| 20 | PIDS_B                    | Supported PIDs [21-40]                  | BitArray              |
| 21 | DISTANCE_W_MIL            | Distance Traveled with MIL on           | Unit.kilometer        |
| 22 | FUEL_RAIL_PRESSURE_VAC    | Fuel Rail Pressure (relative to vacuum) | Unit.kilopascal       |
| 23 | FUEL_RAIL_PRESSURE_DIRECT | Fuel Rail Pressure (direct inject)      | Unit.kilopascal       |
| 24 | O2_S1_WR_VOLTAGE          | 02 Sensor 1 WR Lambda Voltage           | Unit.volt             |
| 25 | O2_S2_WR_VOLTAGE          | 02 Sensor 2 WR Lambda Voltage           | Unit.volt             |
| 26 | O2_S3_WR_VOLTAGE          | 02 Sensor 3 WR Lambda Voltage           | Unit.volt             |
| 27 | O2_S4_WR_VOLTAGE          | 02 Sensor 4 WR Lambda Voltage           | Unit.volt             |
| 28 | O2_S5_WR_VOLTAGE          | 02 Sensor 5 WR Lambda Voltage           | Unit.volt             |
| 29 | O2_S6_WR_VOLTAGE          | 02 Sensor 6 WR Lambda Voltage           | Unit.volt             |
| 2A | O2_S7_WR_VOLTAGE          | 02 Sensor 7 WR Lambda Voltage           | Unit.volt             |
| 2B | O2_S8_WR_VOLTAGE          | 02 Sensor 8 WR Lambda Voltage           | Unit.volt             |
| 2C | COMMANDED_EGR             | Commanded EGR                           | Unit.percent          |
| 2D | EGR_ERROR                 | EGR Error                               | Unit.percent          |
| 2E | EVAPORATIVE_PURGE         | Commanded Evaporative Purge             | Unit.percent          |
| 2F | FUEL_LEVEL                | Fuel Level Input                        | Unit.percent          |
| 30 | WARMUPS_SINCE_DTC_CLEAR   | Number of warm-ups since codes cleared  | Unit.count            |
| 31 | DISTANCE_SINCE_DTC_CLEAR  | Distance traveled since codes cleared   | Unit.kilometer        |
| 32 | EVAP_VAPOR_PRESSURE       | Evaporative system vapor pressure       | Unit.pascal           |
| 33 | BAROMETRIC_PRESSURE       | Barometric Pressure                     | Unit.kilopascal       |
| 34 | O2_S1_WR_CURRENT          | 02 Sensor 1 WR Lambda Current           | Unit.milliampere      |
| 35 | O2_S2_WR_CURRENT          | 02 Sensor 2 WR Lambda Current           | Unit.milliampere      |
| 36 | O2_S3_WR_CURRENT          | 02 Sensor 3 WR Lambda Current           | Unit.milliampere      |
| 37 | O2_S4_WR_CURRENT          | 02 Sensor 4 WR Lambda Current           | Unit.milliampere      |
| 38 | O2_S5_WR_CURRENT          | 02 Sensor 5 WR Lambda Current           | Unit.milliampere      |
| 39 | O2_S6_WR_CURRENT          | 02 Sensor 6 WR Lambda Current           | Unit.milliampere      |
| 3A | O2_S7_WR_CURRENT          | 02 Sensor 7 WR Lambda Current           | Unit.milliampere      |
| 3B | O2_S8_WR_CURRENT          | 02 Sensor 8 WR Lambda Current           | Unit.milliampere      |
| 3C | CATALYST_TEMP_B1S1        | Catalyst Temperature: Bank 1 - Sensor 1 | Unit.celsius          |
| 3D | CATALYST_TEMP_B2S1        | Catalyst Temperature: Bank 2 - Sensor 1 | Unit.celsius          |
| 3E | CATALYST_TEMP_B1S2        | Catalyst Temperature: Bank 1 - Sensor 2 | Unit.celsius          |
| 3F | CATALYST_TEMP_B2S2        | Catalyst Temperature: Bank 2 - Sensor 2 | Unit.celsius          |
| 40 | PIDS_C                    | Supported PIDs [41-60]                  | BitArray              |
| 41 | STATUS_DRIVE_CYCLE        | Monitor status this drive cycle         | [special](Responses.md#status) |
| 42 | CONTROL_MODULE_VOLTAGE    | Control module voltage                  | Unit.volt             |
| 43 | ABSOLUTE_LOAD             | Absolute load value                     | Unit.percent          |
| 44 | COMMANDED_EQUIV_RATIO     | Commanded equivalence ratio             | Unit.ratio            |
| 45 | RELATIVE_THROTTLE_POS     | Relative throttle position              | Unit.percent          |
| 46 | AMBIANT_AIR_TEMP          | Ambient air temperature                 | Unit.celsius          |
| 47 | THROTTLE_POS_B            | Absolute throttle position B            | Unit.percent          |
| 48 | THROTTLE_POS_C            | Absolute throttle position C            | Unit.percent          |
| 49 | ACCELERATOR_POS_D         | Accelerator pedal position D            | Unit.percent          |
| 4A | ACCELERATOR_POS_E         | Accelerator pedal position E            | Unit.percent          |
| 4B | ACCELERATOR_POS_F         | Accelerator pedal position F            | Unit.percent          |
| 4C | THROTTLE_ACTUATOR         | Commanded throttle actuator             | Unit.percent          |
| 4D | RUN_TIME_MIL              | Time run with MIL on                    | Unit.minute           |
| 4E | TIME_SINCE_DTC_CLEARED    | Time since trouble codes cleared        | Unit.minute           |
| 4F | *unsupported*             | *unsupported*                           |                       |
| 50 | MAX_MAF                   | Maximum value for mass air flow sensor  | Unit.grams_per_second |
| 51 | FUEL_TYPE                 | Fuel Type                               | string                |
| 52 | ETHANOL_PERCENT           | Ethanol Fuel Percent                    | Unit.percent          |
| 53 | EVAP_VAPOR_PRESSURE_ABS   | Absolute Evap system Vapor Pressure     | Unit.kilopascal       |
| 54 | EVAP_VAPOR_PRESSURE_ALT   | Evap system vapor pressure              | Unit.pascal           |
| 55 | SHORT_O2_TRIM_B1          | Short term secondary O2 trim - Bank 1   | Unit.percent          |
| 56 | LONG_O2_TRIM_B1           | Long term secondary O2 trim - Bank 1    | Unit.percent          |
| 57 | SHORT_O2_TRIM_B2          | Short term secondary O2 trim - Bank 2   | Unit.percent          |
| 58 | LONG_O2_TRIM_B2           | Long term secondary O2 trim - Bank 2    | Unit.percent          |
| 59 | FUEL_RAIL_PRESSURE_ABS    | Fuel rail pressure (absolute)           | Unit.kilopascal       |
| 5A | RELATIVE_ACCEL_POS        | Relative accelerator pedal position     | Unit.percent          |
| 5B | HYBRID_BATTERY_REMAINING  | Hybrid battery pack remaining life      | Unit.percent          |
| 5C | OIL_TEMP                  | Engine oil temperature                  | Unit.celsius          |
| 5D | FUEL_INJECT_TIMING        | Fuel injection timing                   | Unit.degree           |
| 5E | FUEL_RATE                 | Engine fuel rate                        | Unit.liters_per_hour  |
| 5F | *unsupported*             | *unsupported*                           |                       |

<br>

## Mode 02

Mode 02 commands are the same as mode 01, but are metrics from when the last DTC occurred (the freeze frame). To access them by name, simple prepend `DTC_` to the Mode 01 command name.

```python
import obd

obd.commands.RPM # the Mode 01 command
# vs.
obd.commands.DTC_RPM # the Mode 02 command
```

<br>

## Mode 03

Mode 03 contains a single command `GET_DTC` which requests all diagnostic trouble codes from the vehicle. The response will contain the codes themselves, as well as a description (if python-OBD has one). See the [DTC Responses](Responses.md#diagnostic-trouble-codes-dtcs) section for more details.

|PID  | Name    | Description                             | Response Value        |
|-----|---------|-----------------------------------------|-----------------------|
| N/A | GET_DTC | Get Diagnostic Trouble Codes            | [special](Responses.md#diagnostic-trouble-codes-dtcs) |


<br>

## Mode 04

|PID  | Name      | Description                             | Response Value        |
|-----|-----------|-----------------------------------------|-----------------------|
| N/A | CLEAR_DTC | Clear DTCs and Freeze data              | N/A                   |

<br>

## Mode 06

<span style="color:red">*WARNING: mode 06 is experimental. While it passes software tests, it has not been tested on a real vehicle. Any debug output for this mode would be greatly appreciated.*</span>

Mode 06 commands are used to monitor various test results from the vehicle. All commands in this mode return the same datatype, as described in the [Monitor Response](Responses.md#monitors-mode-06-responses) section. Currently, mode 06 commands are only implemented for CAN protocols (ISO 15765-4).

|PID    | Name                        | Description                                | Response Value        |
|-------|-----------------------------|--------------------------------------------|-----------------------|
| 00    | MIDS_A                      | Supported MIDs [01-20]                     | BitArray              |
| 01    | MONITOR_O2_B1S1             | O2 Sensor Monitor Bank 1 - Sensor 1        | [monitor](Responses.md#monitors-mode-06-responses) |
| 02    | MONITOR_O2_B1S2             | O2 Sensor Monitor Bank 1 - Sensor 2        | [monitor](Responses.md#monitors-mode-06-responses) |
| 03    | MONITOR_O2_B1S3             | O2 Sensor Monitor Bank 1 - Sensor 3        | [monitor](Responses.md#monitors-mode-06-responses) |
| 04    | MONITOR_O2_B1S4             | O2 Sensor Monitor Bank 1 - Sensor 4        | [monitor](Responses.md#monitors-mode-06-responses) |
| 05    | MONITOR_O2_B2S1             | O2 Sensor Monitor Bank 2 - Sensor 1        | [monitor](Responses.md#monitors-mode-06-responses) |
| 06    | MONITOR_O2_B2S2             | O2 Sensor Monitor Bank 2 - Sensor 2        | [monitor](Responses.md#monitors-mode-06-responses) |
| 07    | MONITOR_O2_B2S3             | O2 Sensor Monitor Bank 2 - Sensor 3        | [monitor](Responses.md#monitors-mode-06-responses) |
| 08    | MONITOR_O2_B2S4             | O2 Sensor Monitor Bank 2 - Sensor 4        | [monitor](Responses.md#monitors-mode-06-responses) |
| 09    | MONITOR_O2_B3S1             | O2 Sensor Monitor Bank 3 - Sensor 1        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0A    | MONITOR_O2_B3S2             | O2 Sensor Monitor Bank 3 - Sensor 2        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0B    | MONITOR_O2_B3S3             | O2 Sensor Monitor Bank 3 - Sensor 3        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0C    | MONITOR_O2_B3S4             | O2 Sensor Monitor Bank 3 - Sensor 4        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0D    | MONITOR_O2_B4S1             | O2 Sensor Monitor Bank 4 - Sensor 1        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0E    | MONITOR_O2_B4S2             | O2 Sensor Monitor Bank 4 - Sensor 2        | [monitor](Responses.md#monitors-mode-06-responses) |
| 0F    | MONITOR_O2_B4S3             | O2 Sensor Monitor Bank 4 - Sensor 3        | [monitor](Responses.md#monitors-mode-06-responses) |
| 10    | MONITOR_O2_B4S4             | O2 Sensor Monitor Bank 4 - Sensor 4        | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 20    | MIDS_B                      | Supported MIDs [21-40]                     | BitArray              |
| 21    | MONITOR_CATALYST_B1         | Catalyst Monitor Bank 1                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 22    | MONITOR_CATALYST_B2         | Catalyst Monitor Bank 2                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 23    | MONITOR_CATALYST_B3         | Catalyst Monitor Bank 3                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 24    | MONITOR_CATALYST_B4         | Catalyst Monitor Bank 4                    | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 31    | MONITOR_EGR_B1              | EGR Monitor Bank 1                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 32    | MONITOR_EGR_B2              | EGR Monitor Bank 2                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 33    | MONITOR_EGR_B3              | EGR Monitor Bank 3                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 34    | MONITOR_EGR_B4              | EGR Monitor Bank 4                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 35    | MONITOR_VVT_B1              | VVT Monitor Bank 1                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 36    | MONITOR_VVT_B2              | VVT Monitor Bank 2                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 37    | MONITOR_VVT_B3              | VVT Monitor Bank 3                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 38    | MONITOR_VVT_B4              | VVT Monitor Bank 4                         | [monitor](Responses.md#monitors-mode-06-responses) |
| 39    | MONITOR_EVAP_150            | EVAP Monitor (Cap Off / 0.150\")           | [monitor](Responses.md#monitors-mode-06-responses) |
| 3A    | MONITOR_EVAP_090            | EVAP Monitor (0.090\")                     | [monitor](Responses.md#monitors-mode-06-responses) |
| 3B    | MONITOR_EVAP_040            | EVAP Monitor (0.040\")                     | [monitor](Responses.md#monitors-mode-06-responses) |
| 3C    | MONITOR_EVAP_020            | EVAP Monitor (0.020\")                     | [monitor](Responses.md#monitors-mode-06-responses) |
| 3D    | MONITOR_PURGE_FLOW          | Purge Flow Monitor                         | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 40    | MIDS_C                      | Supported MIDs [41-60]                     | BitArray              |
| 41    | MONITOR_O2_HEATER_B1S1      | O2 Sensor Heater Monitor Bank 1 - Sensor 1 | [monitor](Responses.md#monitors-mode-06-responses) |
| 42    | MONITOR_O2_HEATER_B1S2      | O2 Sensor Heater Monitor Bank 1 - Sensor 2 | [monitor](Responses.md#monitors-mode-06-responses) |
| 43    | MONITOR_O2_HEATER_B1S3      | O2 Sensor Heater Monitor Bank 1 - Sensor 3 | [monitor](Responses.md#monitors-mode-06-responses) |
| 44    | MONITOR_O2_HEATER_B1S4      | O2 Sensor Heater Monitor Bank 1 - Sensor 4 | [monitor](Responses.md#monitors-mode-06-responses) |
| 45    | MONITOR_O2_HEATER_B2S1      | O2 Sensor Heater Monitor Bank 2 - Sensor 1 | [monitor](Responses.md#monitors-mode-06-responses) |
| 46    | MONITOR_O2_HEATER_B2S2      | O2 Sensor Heater Monitor Bank 2 - Sensor 2 | [monitor](Responses.md#monitors-mode-06-responses) |
| 47    | MONITOR_O2_HEATER_B2S3      | O2 Sensor Heater Monitor Bank 2 - Sensor 3 | [monitor](Responses.md#monitors-mode-06-responses) |
| 48    | MONITOR_O2_HEATER_B2S4      | O2 Sensor Heater Monitor Bank 2 - Sensor 4 | [monitor](Responses.md#monitors-mode-06-responses) |
| 49    | MONITOR_O2_HEATER_B3S1      | O2 Sensor Heater Monitor Bank 3 - Sensor 1 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4A    | MONITOR_O2_HEATER_B3S2      | O2 Sensor Heater Monitor Bank 3 - Sensor 2 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4B    | MONITOR_O2_HEATER_B3S3      | O2 Sensor Heater Monitor Bank 3 - Sensor 3 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4C    | MONITOR_O2_HEATER_B3S4      | O2 Sensor Heater Monitor Bank 3 - Sensor 4 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4D    | MONITOR_O2_HEATER_B4S1      | O2 Sensor Heater Monitor Bank 4 - Sensor 1 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4E    | MONITOR_O2_HEATER_B4S2      | O2 Sensor Heater Monitor Bank 4 - Sensor 2 | [monitor](Responses.md#monitors-mode-06-responses) |
| 4F    | MONITOR_O2_HEATER_B4S3      | O2 Sensor Heater Monitor Bank 4 - Sensor 3 | [monitor](Responses.md#monitors-mode-06-responses) |
| 50    | MONITOR_O2_HEATER_B4S4      | O2 Sensor Heater Monitor Bank 4 - Sensor 4 | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 60    | MIDS_D                      | Supported MIDs [61-80]                     | BitArray              |
| 61    | MONITOR_HEATED_CATALYST_B1  | Heated Catalyst Monitor Bank 1             | [monitor](Responses.md#monitors-mode-06-responses) |
| 62    | MONITOR_HEATED_CATALYST_B2  | Heated Catalyst Monitor Bank 2             | [monitor](Responses.md#monitors-mode-06-responses) |
| 63    | MONITOR_HEATED_CATALYST_B3  | Heated Catalyst Monitor Bank 3             | [monitor](Responses.md#monitors-mode-06-responses) |
| 64    | MONITOR_HEATED_CATALYST_B4  | Heated Catalyst Monitor Bank 4             | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 71    | MONITOR_SECONDARY_AIR_1     | Secondary Air Monitor 1                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 72    | MONITOR_SECONDARY_AIR_2     | Secondary Air Monitor 2                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 73    | MONITOR_SECONDARY_AIR_3     | Secondary Air Monitor 3                    | [monitor](Responses.md#monitors-mode-06-responses) |
| 74    | MONITOR_SECONDARY_AIR_4     | Secondary Air Monitor 4                    | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 80    | MIDS_E                      | Supported MIDs [81-A0]                     | BitArray              |
| 81    | MONITOR_FUEL_SYSTEM_B1      | Fuel System Monitor Bank 1                 | [monitor](Responses.md#monitors-mode-06-responses) |
| 82    | MONITOR_FUEL_SYSTEM_B2      | Fuel System Monitor Bank 2                 | [monitor](Responses.md#monitors-mode-06-responses) |
| 83    | MONITOR_FUEL_SYSTEM_B3      | Fuel System Monitor Bank 3                 | [monitor](Responses.md#monitors-mode-06-responses) |
| 84    | MONITOR_FUEL_SYSTEM_B4      | Fuel System Monitor Bank 4                 | [monitor](Responses.md#monitors-mode-06-responses) |
| 85    | MONITOR_BOOST_PRESSURE_B1   | Boost Pressure Control Monitor Bank 1      | [monitor](Responses.md#monitors-mode-06-responses) |
| 86    | MONITOR_BOOST_PRESSURE_B2   | Boost Pressure Control Monitor Bank 1      | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 90    | MONITOR_NOX_ABSORBER_B1     | NOx Absorber Monitor Bank 1                | [monitor](Responses.md#monitors-mode-06-responses) |
| 91    | MONITOR_NOX_ABSORBER_B2     | NOx Absorber Monitor Bank 2                | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| 98    | MONITOR_NOX_CATALYST_B1     | NOx Catalyst Monitor Bank 1                | [monitor](Responses.md#monitors-mode-06-responses) |
| 99    | MONITOR_NOX_CATALYST_B2     | NOx Catalyst Monitor Bank 2                | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| A0    | MIDS_F                      | Supported MIDs [A1-C0]                     | BitArray              |
| A1    | MONITOR_MISFIRE_GENERAL     | Misfire Monitor General Data               | [monitor](Responses.md#monitors-mode-06-responses) |
| A2    | MONITOR_MISFIRE_CYLINDER_1  | Misfire Cylinder 1 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A3    | MONITOR_MISFIRE_CYLINDER_2  | Misfire Cylinder 2 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A4    | MONITOR_MISFIRE_CYLINDER_3  | Misfire Cylinder 3 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A5    | MONITOR_MISFIRE_CYLINDER_4  | Misfire Cylinder 4 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A6    | MONITOR_MISFIRE_CYLINDER_5  | Misfire Cylinder 5 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A7    | MONITOR_MISFIRE_CYLINDER_6  | Misfire Cylinder 6 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A8    | MONITOR_MISFIRE_CYLINDER_7  | Misfire Cylinder 7 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| A9    | MONITOR_MISFIRE_CYLINDER_8  | Misfire Cylinder 8 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| AA    | MONITOR_MISFIRE_CYLINDER_9  | Misfire Cylinder 9 Data                    | [monitor](Responses.md#monitors-mode-06-responses) |
| AB    | MONITOR_MISFIRE_CYLINDER_10 | Misfire Cylinder 10 Data                   | [monitor](Responses.md#monitors-mode-06-responses) |
| AC    | MONITOR_MISFIRE_CYLINDER_11 | Misfire Cylinder 11 Data                   | [monitor](Responses.md#monitors-mode-06-responses) |
| AD    | MONITOR_MISFIRE_CYLINDER_12 | Misfire Cylinder 12 Data                   | [monitor](Responses.md#monitors-mode-06-responses) |
| *gap* |                             |                                            |
| B0    | MONITOR_PM_FILTER_B1        | PM Filter Monitor Bank 1                   | [monitor](Responses.md#monitors-mode-06-responses) |
| B1    | MONITOR_PM_FILTER_B2        | PM Filter Monitor Bank 2                   | [monitor](Responses.md#monitors-mode-06-responses) |

<br>

## Mode 07

The return value will be encoded in the same structure as the Mode 03 `GET_DTC` command.

|PID  | Name            | Description                                  | Response Value        |
|-----|-----------------|----------------------------------------------|-----------------------|
| N/A | GET_CURRENT_DTC | Get DTCs from the current/last driving cycle | [special](Responses.md#diagnostic-trouble-codes-dtcs) |

<br>

## Mode 09

<span style="color:red">*WARNING: mode 09 is experimental. While it has been tested on a hardware simulator, only a subset of the supported
commands have (00-06) been tested. Any debug output for this mode, especially for the untested PIDs, would be greatly appreciated.*</span>

|PID | Name                         | Description                                        | Response Value        |
|----|------------------------------|----------------------------------------------------|-----------------------|
| 00 | PIDS_9A                      | Supported PIDs [01-20]                             | BitArray              |
| 01 | VIN_MESSAGE_COUNT            | VIN Message Count                                  | Unit.count            |
| 02 | VIN                          | Vehicle Identification Number                      | string                |
| 03 | CALIBRATION_ID_MESSAGE_COUNT | Calibration ID message count for PID 04            | Unit.count            |
| 04 | CALIBRATION_ID               | Calibration ID                                     | string                |
| 05 | CVN_MESSAGE_COUNT            | CVN Message Count for PID 06                       | Unit.count            |
| 06 | CVN                          | Calibration Verification Numbers                   | hex string            |
| 07 | PERF_TRACKING_MESSAGE_COUNT  | Performance tracking message count                 | TODO                  |
| 08 | PERF_TRACKING_SPARK          | In-use performance tracking (spark ignition)       | TODO                  |
| 09 | ECU_NAME_MESSAGE_COUNT       | ECU Name Message Count for PID 0A                  | TODO                  |
| 0a | ECU_NAME                     | ECU Name                                           | TODO                  |
| 0b | PERF_TRACKING_COMPRESSION    | In-use performance tracking (compression ignition) | TODO                  |

<br>


---

# Custom Commands

If the command you need is not in python-OBDs tables, you can create a new `OBDCommand` object. The constructor accepts the following arguments (each will become a property).

| Argument             | Type     | Description                                                                |
|----------------------|----------|----------------------------------------------------------------------------|
| name                 | string   | (human readability only)                                                   |
| desc                 | string   | (human readability only)                                                   |
| command              | bytes    | OBD command in hex (typically mode + PID                                   |
| bytes                | int      | Number of bytes expected in response (zero means unknown)                  |
| decoder              | callable | Function used for decoding messages from the OBD adapter                   |
| ecu (optional)       | ECU      | ID of the ECU this command should listen to (`ECU.ALL` by default)         |
| fast (optional)      | bool     | Allows python-OBD to alter this command for efficieny (`False` by default) |
| header (optional)    | string   | If set, use a custom header instead of the default one (7E0)               |


## Example

```python
from obd import OBDCommand, Unit
from obd.protocols import ECU
from obd.utils import bytes_to_int

def rpm(messages):
    """ decoder for RPM messages """
    d = messages[0].data # only operate on a single message
    d = d[2:] # chop off mode and PID bytes
    v = bytes_to_int(d) / 4.0  # helper function for converting byte arrays to ints
    return v * Unit.RPM # construct a Pint Quantity

c = OBDCommand("RPM", \          # name
               "Engine RPM", \   # description
               b"010C", \        # command
               4, \              # number of return bytes to expect
               rpm, \            # decoding function
               ECU.ENGINE, \     # (optional) ECU filter
               True)             # (optional) allow a "01" to be added for speed
```

By default, custom commands will be treated as "unsupported by the vehicle". There are two ways to handle this:

```python
o = obd.OBD()

# use the `force` parameter when querying
o.query(c, force=True)

# OR

# add your command to the set of supported commands
o.supported_commands.add(c)
o.query(c)
```

<br>

Here are some details on the less intuitive fields of an OBDCommand:

---

## OBDCommand.decoder

The `decoder` argument is a function of following form.

```python
def <name>(<list_of_messages>):
    ...
    return <value>
```

The return value of your decoder will be loaded into the `OBDResponse.value` field. Decoders are given a list of `Message` objects as an argument. If your decoder is called, this list is garaunteed to have at least one message object. Each `Message` object has a `data` property, which holds a parsed bytearray, and is also garauteed to have the number of bytes specified by the command. This bytearray includes any mode and PID bytes in the vehicle's response.

*NOTE: If you are transitioning from an older version of Python-OBD (where decoders were given raw hex strings as arguments), you can use the `Message.hex()` function as a patch.*

```python
def <name>(messages):
    _hex = messages[0].hex()
    ...
    return <value>
```

*You can also access the original string sent by the adapter using the `Message.raw()` function.*

---

## OBDCommand.ecu

The `ecu` argument is a constant used to filter incoming messages. Some commands may listen to multiple ECUs (such as DTC decoders), where others may only be concerned with the engine (such as RPM). Currently, python-OBD can only distinguish the engine, but this list may be expanded over time:

- `ECU.ALL`
- `ECU.ALL_KNOWN`
- `ECU.UNKNOWN`
- `ECU.ENGINE`

---

## OBDCommand.fast

The optional `fast` argument tells python-OBD whether it is safe to append a `"01"` to the end of the command. This will instruct the adapter to return the first response it recieves, rather than waiting for more (and eventually reaching a timeout). This can speed up requests significantly, and is enabled for most of python-OBDs internal commands. However, for unusual commands, it is safest to leave this disabled.

---

## OBDCommand.header

The optional `header` argument tells python-OBD to use a custom header when querying the command. If not set, python-OBD assumes that the default 7E0 header is needed for querying the command. The switch between default and custom header (and vice versa) is automatically done by python-OBD.

---

<br>


---

# Debug Output

If python-OBD is not working properly, the first thing you should do is enable debug output. Add the following line before your connection code to print all of the debug information to your console:

```python
obd.logger.setLevel(obd.logging.DEBUG)
```

Here are some common logs from python-OBD, and their meanings:

<br>

### Successful Connection

```none
[obd] ========================== python-OBD (v0.4.0) ==========================
[obd] Explicit port defined
[obd] Opening serial port '/dev/pts/2'
[obd] Serial port successfully opened on /dev/pts/2
[obd] write: 'ATZ\r\n'
[obd] wait: 1 seconds
[obd] read: 'ATZ\rELM327 v2.1\r'
[obd] write: 'ATE0\r\n'
[obd] read: 'ATE0\rOK\r'
[obd] write: 'ATH1\r\n'
[obd] read: 'OK\r'
[obd] write: 'ATL0\r\n'
[obd] read: 'OK\r'
[obd] write: 'ATSPA8\r\n'
[obd] read: 'OK\r'
[obd] write: '0100\r\n'
[obd] read: '7E8 06 41 00 FF FF FF FF FC\r'
[obd] write: 'ATDPN\r\n'
[obd] read: 'A8\r'
[obd] Connection successful
[obd] querying for supported PIDs (commands)...
[obd] Sending command: 0100: Supported PIDs [01-20]
[obd] write: '0100\r\n'
[obd] read: '7E8 06 41 00 FF FF FF FF FC\r'
[obd] Sending command: 0120: Supported PIDs [21-40]
[obd] write: '0120\r\n'
[obd] read: '7E8 06 41 20 FF FF FF FF FC\r'
[obd] Sending command: 0140: Supported PIDs [41-60]
[obd] write: '0140\r\n'
[obd] read: '7E8 06 41 40 FF FF FF FE FB\r'
[obd] finished querying with 93 commands supported
[obd] =========================================================================
```

<br>

### Unresponsive ELM

```none
[obd] ========================== python-OBD (v0.4.0) ==========================
[obd] Explicit port defined
[obd] Opening serial port '/dev/pts/2'
[obd] Serial port successfully opened on /dev/pts/2
[obd] write: 'ATZ\r\n'
[obd] wait: 1 seconds
[obd] __read() found nothing
[obd] __read() found nothing
[obd] __read() never recieved prompt character
[obd] read: ''
[obd] write: 'ATE0\r\n'
[obd] __read() found nothing
[obd] __read() found nothing
[obd] __read() never recieved prompt character
[obd] read: ''
[obd] Connection Error:
[obd]     ATE0 did not return 'OK'
[obd] Failed to connect
[obd] =========================================================================
```

This is likely a problem with the serial connection between the OBD-II adapter and your computer. Make sure that:

- bluetooth devices have been paired properly
- you are connecting to the right port in `/dev` (or that there is any port at all)
- you have the correct permissions to write to the port

You can use the `scan_serial()` helper function to determine which ports are available for writing.

```python
import obd

ports = obd.scan_serial()       # return list of valid USB or RF ports
print ports                    # ['/dev/ttyUSB0', '/dev/ttyUSB1']
```

<br>

### Unresponsive Vehicle

```none
[obd] ========================== python-OBD (v0.4.0) ==========================
[obd] Explicit port defined
[obd] Opening serial port '/dev/pts/2'
[obd] Serial port successfully opened on /dev/pts/2
[obd] write: 'ATZ\r\n'
[obd] wait: 1 seconds
[obd] read: 'ATZ\rELM327 v2.1\r'
[obd] write: 'ATE0\r\n'
[obd] read: 'ATE0\rOK\r'
[obd] write: 'ATH1\r\n'
[obd] read: 'OK\r'
[obd] write: 'ATL0\r\n'
[obd] read: 'OK\r'
[obd] write: 'ATSPA8\r\n'
[obd] read: 'OK\r'
[obd] write: '0100\r\n'
[obd] read: 'SEARCHING...\rUNABLE TO CONNECT\r'
[obd] write: 'ATDPN\r\n'
[obd] read: '0\r'
[obd] Connection Error:
[obd]     ELM responded with unknown protocol
[obd] Failed to connect
[obd] =========================================================================
```

This is a connection problem between the ELM adapter and your car. Make sure that you car is powered, and that the electrical connection between the adapter and your car's OBD-II port is sound.

---

<br>


---

# Debug

python-OBD uses python's builtin logging system. By default, it is setup to send output to `stderr` with a level of WARNING. The module's logger can be accessed via the `logger` variable at the root of the module. For instance, to enable console printing of all debug messages, use the following snippet:

```python
import obd

obd.logger.setLevel(obd.logging.DEBUG) # enables all debug information
```

Or, to silence all logging output from python-OBD:

```python
import obd

obd.logger.removeHandler(obd.console_handler)
```

---

<br>
