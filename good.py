import sys
import sqlite3
import os
import getpass
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# ---------- سیستم اسکیل ریسپانسیو ----------
def get_scale_factor():
    """محاسبه ضریب اسکیل فقط بر اساس ارتفاع فیزیکی صفحه.
    Qt خودش DPI scaling ویندوز رو هندل می‌کنه، پس ما نباید دوباره DPI رو حساب کنیم."""
    app = QApplication.instance()
    if not app:
        return 1.0
    screen = app.primaryScreen()
    if not screen:
        return 1.0
    # از availableGeometry استفاده می‌کنیم که Qt قبلاً DPI-aware کردتش
    height = screen.availableGeometry().height()
    # 900px = مرجع (مانیتور ۲۲ اینچ معمولی)
    # زیر 700: لپتاپ کوچیک → 0.78
    # 700-850: لپتاپ ۱۵ اینچ → 0.85-0.95
    # 850-1000: مانیتور معمولی → 1.0
    # بالای 1000: مانیتور بزرگ → 1.1+
    scale = height / 900.0
    return max(0.72, min(1.25, scale))

# متغیر گلوبال اسکیل - بعد از ساخت QApplication مقداردهی می‌شه
_SCALE = 1.0

def s(value):
    """اسکیل کردن یک عدد (پیکسل، فونت‌سایز و غیره)"""
    return int(value * _SCALE)

# ---------- دیکشنری تعطیلات رسمی ----------
HOLIDAYS = {
    "01-01": "عید نوروز - سال نو",
    "01-02": "عید نوروز",
    "01-03": "عید نوروز",
    "01-04": "عید نوروز",
    "01-12": "روز جمهوری اسلامی",
    "01-13": "سیزده بدر",
    "03-14": "رحلت امام خمینی",
    "03-15": "قیام ۱۵ خرداد",
    "06-16": "شهادت امام رضا (ع)",
    "10-14": "ولادت حضرت مسیح",
    "10-15": "ولادت حضرت مسیح",
    "11-22": "پیروزی انقلاب اسلامی",
    "11-23": "پیروزی انقلاب اسلامی",
    "12-29": "ملی شدن صنعت نفت",
}

# ---------- دیکشنری مناسبت‌های غیرتعطیل ----------
EVENTS = {
    "08-21": "روز بزرگداشت حافظ",
    "08-25": "روز بزرگداشت فردوسی",
    "09-30": "روز بزرگداشت مولوی",
    "10-20": "ولادت حضرت زینب (س) - روز پرستار",
    "11-05": "ولادت حضرت علی (ع) - روز پدر",
    "12-20": "ولادت حضرت فاطمه (س) - روز مادر",
    "02-28": "روز جهانی زن",
    "03-21": "روز جهانی قدس",
    "04-14": "روز معلم",
    "05-05": "روز جهانی محیط زیست",
}

# ---------- توابع مدیریت استارتاپ ----------
def add_to_startup():
    username = getpass.getuser()
    startup_path = f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(__file__)
    bat_path = os.path.join(startup_path, "TaskCalendar.bat")
    with open(bat_path, "w") as f:
        f.write(f'start "" "{exe_path}"')
    return bat_path

def remove_from_startup():
    username = getpass.getuser()
    bat_path = f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Startup\\TaskCalendar.bat"
    if os.path.exists(bat_path):
        os.remove(bat_path)

def is_in_startup():
    username = getpass.getuser()
    bat_path = f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Startup\\TaskCalendar.bat"
    return os.path.exists(bat_path)

# ---------- توابع تشخیص تعطیلی ----------
def is_holiday(year, month, day):
    import jdatetime
    jd = jdatetime.date(year, month, day)
    
    if jd.weekday() == 6:
        return True
    
    key = f"{month:02d}-{day:02d}"
    if key in HOLIDAYS:
        return True
    
    return False

def get_days_in_month(year, month):
    if month <= 6:
        return 31
    elif month <= 11:
        return 30
    else:
        return 29


# ---------- دیتابیس ----------
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("tasks.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                status INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS deleted_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                deleted_date TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def add_task(self, date, text):
        self.cursor.execute("INSERT INTO tasks (date, text) VALUES (?, ?)", (date, text))
        self.conn.commit()

    def get_tasks(self, date):
        self.cursor.execute("SELECT id, text, status FROM tasks WHERE date = ?", (date,))
        return self.cursor.fetchall()

    def get_deleted_tasks(self, date):
        self.cursor.execute("SELECT id, text, deleted_date FROM deleted_tasks WHERE date = ? ORDER BY deleted_date DESC", (date,))
        return self.cursor.fetchall()

    def move_to_deleted(self, task_id, task_text, date):
        now = datetime.now().strftime("%H:%M:%S")
        self.cursor.execute("INSERT INTO deleted_tasks (date, text, deleted_date) VALUES (?, ?, ?)", 
                           (date, task_text, now))
        self.cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def delete_all_deleted_tasks(self, date):
        self.cursor.execute("DELETE FROM deleted_tasks WHERE date = ?", (date,))
        self.conn.commit()

    def toggle_status(self, task_id, current_status):
        new_status = 0 if current_status == 1 else 1
        self.cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
        self.conn.commit()
        return new_status

    def get_all_dates_with_tasks(self):
        self.cursor.execute("SELECT DISTINCT date FROM tasks")
        return [row[0] for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close()


# ---------- آیتم سفارشی برای لیست تسک‌ها ----------
class TaskWidgetItem(QWidget):
    def __init__(self, task_id, task_text, status, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.task_text = task_text
        self.parent_list = parent
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(s(5), s(5), s(5), s(5))
        layout.setSpacing(s(8))
        
        self.label = QLabel(task_text)
        if parent and hasattr(parent, 'persian_font'):
            self.label.setFont(parent.persian_font)
        self.label.setStyleSheet(f"color: white; font-size: {s(12)}px; font-weight: 500;")
        if status == 1:
            font = self.label.font()
            font.setStrikeOut(True)
            self.label.setFont(font)
            self.label.setStyleSheet(f"color: #888888; font-size: {s(12)}px; font-weight: 500;")
        
        delete_btn = QPushButton("✖")
        delete_btn.setFixedSize(s(22), s(22))
        delete_btn.setFont(self.label.font())
        r = s(11)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ff4757;
                color: white;
                border-radius: {r}px;
                font-size: {s(10)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #ff6b81;
            }}
        """)
        delete_btn.clicked.connect(self.delete_task)
        
        layout.addWidget(delete_btn)
        layout.addWidget(self.label)
        layout.addStretch()
        
        self.label.mouseDoubleClickEvent = self.toggle_status
    
    def delete_task(self):
        if hasattr(self.parent_list, 'on_task_deleted'):
            self.parent_list.on_task_deleted(self.task_id, self.task_text)
    
    def toggle_status(self, event):
        if hasattr(self.parent_list, 'on_task_toggled'):
            current_strike = self.label.font().strikeOut()
            self.parent_list.on_task_toggled(self.task_id, not current_strike)


# ---------- لیست سفارشی برای تسک‌ها ----------
class TaskListWidget(QListWidget):
    def __init__(self, db, date_str, on_delete_callback, on_toggle_callback, parent=None):
        super().__init__(parent)
        self.db = db
        self.date_str = date_str
        self.on_delete_callback = on_delete_callback
        self.on_toggle_callback = on_toggle_callback
        self.persian_font = parent.persian_font if parent and hasattr(parent, 'persian_font') else None
    
    def on_task_deleted(self, task_id, task_text):
        self.on_delete_callback(task_id, task_text)
    
    def on_task_toggled(self, task_id, new_status):
        self.on_toggle_callback(task_id, new_status)
    
    def load_tasks(self):
        self.clear()
        tasks = self.db.get_tasks(self.date_str)
        for task_id, text, status in tasks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, s(35)))
            widget = TaskWidgetItem(task_id, text, status, self)
            self.addItem(item)
            self.setItemWidget(item, widget)
            item.setData(Qt.UserRole, task_id)


# ---------- ویجت تقویم ----------
class CalendarWidget(QWidget):
    def __init__(self, db, on_date_selected, on_today_clicked, parent=None):
        super().__init__(parent)
        self.db = db
        self.on_date_selected = on_date_selected
        self.on_today_clicked = on_today_clicked
        import jdatetime
        self.current_jdate = jdatetime.date.today()
        self.selected_jdate = jdatetime.date.today()
        self.task_dates = []
        self.persian_font = parent.persian_font if parent and hasattr(parent, 'persian_font') else None
        self.initUI()
        self.update_calendar()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(s(5), s(5), s(5), s(5))
        layout.setSpacing(s(5))

        control_bar = QHBoxLayout()
        
        self.today_btn = QPushButton("امروز")
        self.today_btn.setFixedHeight(s(28))
        self.today_btn.clicked.connect(self.go_to_today)
        control_bar.addWidget(self.today_btn)
        control_bar.addStretch()
        
        self.prev_month_btn = QPushButton("▶")
        self.prev_month_btn.clicked.connect(self.prev_month)
        control_bar.addWidget(self.prev_month_btn)
        
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignCenter)
        control_bar.addWidget(self.month_label)
        
        self.next_month_btn = QPushButton("◀")
        self.next_month_btn.clicked.connect(self.next_month)
        control_bar.addWidget(self.next_month_btn)
        
        layout.addLayout(control_bar)

        week_layout = QHBoxLayout()
        week_layout.setSpacing(4)
        week_layout.setContentsMargins(s(5), 0, s(5), 0)
        week_days = ["جمعه", "پنجشنبه", "چهارشنبه", "سه‌شنبه", "دوشنبه", "یکشنبه", "شنبه"]
        for day in week_days:
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignCenter)
            if day == "جمعه":
                lbl.setStyleSheet(f"color: #ff6b6b; font-size: {s(10)}px; font-weight: bold;")
            else:
                lbl.setStyleSheet(f"color: #00E5FF; font-size: {s(10)}px; font-weight: bold;")
            week_layout.addWidget(lbl)
        layout.addLayout(week_layout)

        self.day_grid_layout = QGridLayout()
        self.day_grid_layout.setHorizontalSpacing(4)
        self.day_grid_layout.setVerticalSpacing(4)
        self.day_grid_layout.setContentsMargins(s(5), s(5), s(5), s(5))
        layout.addLayout(self.day_grid_layout)

    def go_to_today(self):
        import jdatetime
        self.current_jdate = jdatetime.date.today()
        self.selected_jdate = jdatetime.date.today()
        self.update_calendar()
        self.on_today_clicked()

    def load_task_dates(self):
        self.task_dates = self.db.get_all_dates_with_tasks()

    def clear_grid(self):
        while self.day_grid_layout.count():
            item = self.day_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def update_calendar(self):
        import jdatetime
        self.clear_grid()
        
        self.load_task_dates()

        year = self.current_jdate.year
        month = self.current_jdate.month

        first_day = jdatetime.date(year, month, 1)
        start_weekday = first_day.weekday()
        days_in_month = get_days_in_month(year, month)

        month_names = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", 
                      "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        self.month_label.setText(f"{month_names[month - 1]} {year}")

        total_cells = start_weekday + days_in_month
        rows_needed = (total_cells + 6) // 7

        day = 1

        # اندازه دکمه رو از عرض پنجره حساب می‌کنیم
        # عرض window منهای margin ها تقسیم بر ۷ ستون
        try:
            win = self.window()
            available_w = win.width() - s(50)
        except Exception:
            available_w = 300
        cell_w = max(s(26), (available_w - 4 * 6) // 7)
        cell_h = max(s(26), int(cell_w * 0.85))

        for row in range(rows_needed):
            for col in range(7):
                btn = QPushButton()
                btn.setFixedSize(cell_w, cell_h)
                
                if row == 0 and col < start_weekday:
                    btn.setEnabled(False)
                    btn.setStyleSheet("background: transparent; border: none;")
                    btn.setText("")
                elif day <= days_in_month:
                    btn.setText(str(day))
                    date_str = f"{year}-{month}-{day}"
                    btn.setProperty("date", date_str)
                    btn.clicked.connect(self.make_handler(date_str))
                    
                    current_jd = jdatetime.date(year, month, day)
                    r = max(4, cell_h // 5)
                    fs = max(9, cell_h // 3)
                    
                    if current_jd == jdatetime.date.today():
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: rgba(0,229,255,40);
                                color: #00E5FF;
                                border-radius: {r}px;
                                font-weight: bold;
                                font-size: {fs}px;
                                border: 1px solid #00E5FF;
                            }}
                            QPushButton:hover {{
                                background-color: rgba(0,229,255,60);
                            }}
                        """)
                    elif current_jd == self.selected_jdate:
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #00E5FF;
                                color: #1a1a2e;
                                border-radius: {r}px;
                                font-weight: bold;
                                font-size: {fs}px;
                            }}
                        """)
                    elif is_holiday(year, month, day):
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: rgba(0,0,0,60);
                                color: #ff6b6b;
                                border-radius: {r}px;
                                font-weight: bold;
                                font-size: {fs}px;
                            }}
                            QPushButton:hover {{
                                background-color: rgba(255,107,107,30);
                            }}
                        """)
                    else:
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: rgba(0,0,0,60);
                                color: white;
                                border-radius: {r}px;
                                font-weight: bold;
                                font-size: {fs}px;
                            }}
                            QPushButton:hover {{
                                background-color: rgba(0,229,255,30);
                            }}
                        """)
                    
                    if date_str in self.task_dates:
                        btn.setStyleSheet(btn.styleSheet() + """
                            border-bottom: 2px solid #00E5FF;
                        """)
                    
                    day += 1
                else:
                    btn.setEnabled(False)
                    btn.setStyleSheet("background: transparent; border: none;")
                    btn.setText("")
                
                self.day_grid_layout.addWidget(btn, row, 6 - col)

    def make_handler(self, date_str):
        def handler():
            parts = date_str.split('-')
            import jdatetime
            d = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            self.selected_jdate = d
            self.on_date_selected(d)
            self.update_calendar()
        return handler

    def prev_month(self):
        import jdatetime
        if self.current_jdate.month == 1:
            self.current_jdate = jdatetime.date(self.current_jdate.year - 1, 12, 1)
        else:
            self.current_jdate = jdatetime.date(self.current_jdate.year, self.current_jdate.month - 1, 1)
        self.update_calendar()

    def next_month(self):
        import jdatetime
        if self.current_jdate.month == 12:
            self.current_jdate = jdatetime.date(self.current_jdate.year + 1, 1, 1)
        else:
            self.current_jdate = jdatetime.date(self.current_jdate.year, self.current_jdate.month + 1, 1)
        self.update_calendar()


# ---------- ویجت اصلی ----------
class MainWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        import jdatetime
        self.current_jdate = jdatetime.date.today()
        self.drag_pos = None
        self.dragging = False
        self.persian_font = None
        self.initUI()
        self.load_tasks()
        self.load_deleted_tasks()
        self.start_clock()
        self.create_system_tray()

    def create_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = self.get_icon_path()
        if icon_path and os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setFont(QFont("Segoe UI", 20))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "C")
            painter.end()
            self.tray_icon.setIcon(QIcon(pixmap))
        tray_menu = QMenu()
        show_action = QAction("نمایش ویجت", self)
        show_action.triggered.connect(self.show_widget)
        tray_menu.addAction(show_action)
        hide_action = QAction("مخفی کردن ویجت", self)
        hide_action.triggered.connect(self.hide_widget)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addSeparator()
        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self.close_app)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide_widget()
            else:
                self.show_widget()
    
    def show_widget(self):
        self.show()
        self.raise_()
    
    def hide_widget(self):
        self.hide()

    def get_icon_path(self):
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "logo.ico"),
            os.path.join(os.path.dirname(__file__), "icon.ico"),
            os.path.join(os.path.dirname(__file__), "app.ico"),
            os.path.join(os.path.dirname(__file__), "Logo", "logo.ico"),
            os.path.join(os.path.dirname(__file__), "icons", "logo.ico"),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible_paths.append(os.path.join(sys._MEIPASS, "logo.ico"))
            possible_paths.append(os.path.join(sys._MEIPASS, "icon.ico"))
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        return None

    def get_font_path(self):
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "fonts", "IranYekan.ttf"),
            os.path.join(os.path.dirname(__file__), "IranYekan.ttf"),
            os.path.expanduser("~/Desktop/IranYekan.ttf"),
            "C:/Windows/Fonts/IranYekan.ttf"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def on_today_clicked(self):
        import jdatetime
        self.current_jdate = jdatetime.date.today()
        self.update_display()

    def show_event_for_date(self, jdate):
        key = f"{jdate.month:02d}-{jdate.day:02d}"
        weekday_names = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
        weekday = jdate.weekday()
        
        event_text = ""
        
        if key in HOLIDAYS:
            event_text = f"{HOLIDAYS[key]} (تعطیل رسمی)"
        elif key in EVENTS:
            event_text = f"{EVENTS[key]}"
        elif weekday == 6:
            event_text = "روز تعطیل (جمعه)"
        else:
            event_text = "روز عادی - بدون مناسبت خاص"
        
        self.event_box.setText(f"{weekday_names[weekday]} - {event_text}")

    def update_display(self):
        import jdatetime
        weekday_fa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
        current_weekday = weekday_fa[self.current_jdate.weekday()]
        date_text = f"{current_weekday}\n{self.current_jdate.year}/{self.current_jdate.month}/{self.current_jdate.day}"
        self.date_label.setText(date_text)
        
        # اضافه کردن آیکون 📅 و تاریخ به عنوان لیست کارها
        self.active_label.setText(f"📅 لیست کارهای {current_weekday} - {self.current_jdate.year}/{self.current_jdate.month}/{self.current_jdate.day}")
        
        self.load_tasks()
        self.load_deleted_tasks()
        self.calendar_widget.selected_jdate = self.current_jdate
        self.calendar_widget.update_calendar()
        self.show_event_for_date(self.current_jdate)

    def update_startup_button(self):
        if hasattr(self, 'startup_btn'):
            if is_in_startup():
                self.startup_btn.setText("✅")
                self.startup_btn.setToolTip("فعال - کلیک کنید تا غیرفعال شود")
            else:
                self.startup_btn.setText("⚙️")
                self.startup_btn.setToolTip("غیرفعال - کلیک کنید تا فعال شود")

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            screen_height = screen_rect.height()
            screen_width = screen_rect.width()
        else:
            screen_height = 768
            screen_width = 1366
        
        # پنجره تمام ارتفاع صفحه رو می‌گیره
        new_width = max(320, min(520, int(screen_width * 0.30)))
        new_height = screen_height  # تمام ارتفاع موجود
        
        self.setMinimumSize(300, 500)
        self.setMaximumSize(560, screen_height)
        self.resize(new_width, new_height)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 100))

        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setGraphicsEffect(shadow)
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("""
            #CentralWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30, 30, 60, 230), stop:1 rgba(20, 20, 50, 230));
                border-radius: 25px;
                border: 1px solid rgba(0, 225, 255, 100);
            }
        """)

        font_path = self.get_font_path()
        if font_path and os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                self.persian_font = QFont(font_family, s(11))
                QApplication.setFont(self.persian_font)
            else:
                self.persian_font = QFont("Segoe UI", s(11))
        else:
            self.persian_font = QFont("Segoe UI", s(11))

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ScrollArea برای اینکه روی صفحه‌های کوچیک هم همه المان‌ها نمایش داده بشن
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,10);
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,229,255,120);
                border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(scroll_content)
        inner_layout.setContentsMargins(s(15), s(10), s(15), s(15))
        inner_layout.setSpacing(s(8))

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # از این به بعد همه المان‌ها به inner_layout اضافه میشن
        layout = inner_layout

        title_bar = QFrame()
        title_bar.setFixedHeight(s(55))
        title_bar.setStyleSheet("background-color: rgba(0,0,0,0); border: none;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(s(8), 0, s(8), 0)
        logo_label = QLabel("🗓️")
        logo_label.setFont(QFont("Segoe UI", s(22)))
        logo_label.setStyleSheet("color: #00E5FF;")
        logo_label.setFixedSize(s(42), s(42))
        title_layout.addWidget(logo_label)

        app_name = QLabel("TaskCalendar")
        app_name.setFont(self.persian_font)
        app_name.setStyleSheet(f"color: #FFFFFF; font-size: {s(14)}px; font-weight: bold;")
        title_layout.addWidget(app_name)

        title_layout.addStretch()

        self.clock_label = QLabel()
        self.clock_label.setAlignment(Qt.AlignCenter)
        self.clock_label.setFont(self.persian_font)
        self.clock_label.setStyleSheet(f"color: #00E5FF; font-size: {s(26)}px; font-weight: bold;")
        title_layout.addWidget(self.clock_label)

        title_layout.addStretch()

        self.startup_btn = QPushButton("⚙️")
        self.startup_btn.setFixedSize(s(35), s(35))
        self.startup_btn.setStyleSheet(f"background-color: transparent; color: #00E5FF; border-radius: {s(17)}px; font-size: {s(16)}px;")
        self.startup_btn.clicked.connect(self.ask_startup)
        title_layout.addWidget(self.startup_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(s(35), s(35))
        close_btn.setFont(self.persian_font)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ff4757;
                color: white;
                border-radius: {s(17)}px;
                font-weight: bold;
                font-size: {s(16)}px;
            }}
            QPushButton:hover {{
                background-color: #ff6b81;
            }}
        """)
        close_btn.clicked.connect(self.hide_widget)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        import jdatetime
        weekday_fa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
        current_weekday = weekday_fa[self.current_jdate.weekday()]
        date_text = f"{current_weekday}\n{self.current_jdate.year}/{self.current_jdate.month}/{self.current_jdate.day}"
        
        self.date_label = QLabel(date_text)
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setFont(self.persian_font)
        self.date_label.setStyleSheet(f"""
            color: #FFFFFF;
            font-size: {s(20)}px;
            font-weight: bold;
            margin: {s(6)}px;
        """)
        layout.addWidget(self.date_label)

        calendar_label = QLabel("تقویم ماه")
        calendar_label.setAlignment(Qt.AlignCenter)
        calendar_label.setFont(self.persian_font)
        calendar_label.setStyleSheet(f"color: #00E5FF; font-size: {s(12)}px; font-weight: bold; margin-top: {s(2)}px;")
        layout.addWidget(calendar_label)

        self.calendar_widget = CalendarWidget(self.db, self.on_date_selected, self.on_today_clicked, self)
        layout.addWidget(self.calendar_widget)

        event_label = QLabel("مناسبت روز")
        event_label.setStyleSheet(f"color: #00E5FF; font-size: {s(12)}px; font-weight: bold; margin-top: {s(5)}px;")
        layout.addWidget(event_label)

        self.event_box = QTextEdit()
        self.event_box.setPlaceholderText("با کلیک روی هر روز، مناسبت آن نمایش داده می‌شود...")
        self.event_box.setMaximumHeight(s(60))
        self.event_box.setReadOnly(True)
        self.event_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: rgba(0, 0, 0, 60);
                border-radius: {s(10)}px;
                padding: {s(8)}px;
                color: #cccccc;
                font-size: {s(11)}px;
                border: none;
            }}
        """)
        layout.addWidget(self.event_box)

        input_label = QLabel("تسک جدید")
        input_label.setFont(self.persian_font)
        input_label.setStyleSheet(f"color: #00E5FF; font-size: {s(12)}px; font-weight: bold; margin-top: {s(5)}px;")
        layout.addWidget(input_label)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(s(6))
        
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("متن تسک را وارد کنید...")
        self.task_input.setFont(self.persian_font)
        self.task_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(255,255,255,60);
                border-radius: {s(20)}px;
                padding: {s(8)}px {s(12)}px;
                color: white;
                font-size: {s(12)}px;
                border: none;
            }}
        """)
        self.task_input.returnPressed.connect(self.add_task)
        
        add_btn = QPushButton("اضافه کن")
        add_btn.setFixedSize(s(85), s(36))
        add_btn.setFont(self.persian_font)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #00E5FF;
                color: #1a1a2e;
                border-radius: {s(18)}px;
                font-size: {s(11)}px;
                font-weight: bold;
            }}
        """)
        add_btn.clicked.connect(self.add_task)
        
        input_layout.addWidget(self.task_input)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)

        self.active_label = QLabel("📅 لیست کارهای امروز")
        self.active_label.setAlignment(Qt.AlignCenter)
        self.active_label.setFont(self.persian_font)
        self.active_label.setStyleSheet(f"color: #FFFFFF; font-size: {s(12)}px; font-weight: bold; margin-top: {s(5)}px;")
        layout.addWidget(self.active_label)

        gregorian = self.current_jdate.togregorian()
        date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
        
        self.task_list = TaskListWidget(self.db, date_str, self.on_task_deleted, self.on_task_toggled, self)
        self.task_list.setFont(self.persian_font)
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 0, 0, 100);
                border-radius: 10px;
                padding: 5px;
                border: none;
            }
        """)
        self.task_list.setMinimumHeight(s(100))
        layout.addWidget(self.task_list)

        deleted_header_layout = QHBoxLayout()
        deleted_label = QLabel("تسک‌های حذف شده")
        deleted_label.setFont(self.persian_font)
        deleted_label.setStyleSheet(f"color: #ff6b6b; font-size: {s(11)}px; font-weight: bold;")
        deleted_header_layout.addWidget(deleted_label)
        deleted_header_layout.addStretch()
        
        self.clear_deleted_btn = QPushButton("حذف همه")
        self.clear_deleted_btn.setFixedSize(s(85), s(26))
        self.clear_deleted_btn.setFont(self.persian_font)
        self.clear_deleted_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 107, 107, 80);
                color: #ff6b6b;
                border-radius: {s(13)}px;
                font-size: {s(10)}px;
                font-weight: bold;
            }}
        """)
        self.clear_deleted_btn.clicked.connect(self.clear_all_deleted_tasks)
        deleted_header_layout.addWidget(self.clear_deleted_btn)
        layout.addLayout(deleted_header_layout)

        self.deleted_list = QListWidget()
        self.deleted_list.setFont(self.persian_font)
        self.deleted_list.setStyleSheet(f"""
            QListWidget {{
                background-color: rgba(0, 0, 0, 80);
                border-radius: {s(10)}px;
                padding: {s(5)}px;
                color: #cccccc;
                font-size: {s(10)}px;
                border: none;
            }}
        """)
        self.deleted_list.setMaximumHeight(s(75))
        layout.addWidget(self.deleted_list)

        footer_label = QLabel("made by kamyar shishehgaran")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setFont(self.persian_font)
        footer_label.setStyleSheet(f"color: rgba(255,255,255,40); font-size: {s(9)}px; margin-top: {s(4)}px;")
        layout.addWidget(footer_label)

        title_bar.mousePressEvent = self.start_move
        title_bar.mouseMoveEvent = self.do_move
        title_bar.mouseReleaseEvent = self.stop_move
        
        self.update_startup_button()
        self.show_event_for_date(self.current_jdate)

    def ask_startup(self):
        if is_in_startup():
            reply = QMessageBox.question(self, "تنظیمات استارتاپ", 
                                         "آیا می‌خواهید برنامه هنگام روشن شدن ویندوز اجرا نشود؟",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                remove_from_startup()
                QMessageBox.information(self, "تنظیمات استارتاپ", "✅ برنامه از استارتاپ ویندوز حذف شد")
        else:
            reply = QMessageBox.question(self, "تنظیمات استارتاپ", 
                                         "آیا می‌خواهید برنامه هنگام روشن شدن ویندوز به صورت خودکار اجرا شود؟",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                add_to_startup()
                QMessageBox.information(self, "تنظیمات استارتاپ", "✅ برنامه به استارتاپ ویندوز اضافه شد\nاز دفعه بعد با روشن شدن ویندوز اجرا می‌شود")
        
        self.update_startup_button()

    def on_date_selected(self, selected_jdate):
        self.current_jdate = selected_jdate
        self.update_display()

    def load_tasks(self):
        gregorian = self.current_jdate.togregorian()
        date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
        self.task_list.date_str = date_str
        self.task_list.load_tasks()
        self.calendar_widget.load_task_dates()
        self.calendar_widget.update_calendar()

    def load_deleted_tasks(self):
        self.deleted_list.clear()
        gregorian = self.current_jdate.togregorian()
        date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
        tasks = self.db.get_deleted_tasks(date_str)
        for _, text, deleted_date in tasks:
            item = QListWidgetItem(f"✖ {text}  [{deleted_date}]")
            item.setForeground(QColor(160, 160, 160))
            self.deleted_list.addItem(item)

    def clear_all_deleted_tasks(self):
        if self.deleted_list.count() == 0:
            QMessageBox.information(self, "تسک‌های حذف شده", "هیچ تسک حذف شده‌ای وجود ندارد!")
            return
        reply = QMessageBox.question(self, "تایید حذف", 
                                     "آیا از حذف همه تسک‌های حذف شده اطمینان دارید؟\nاین عمل قابل بازگشت نیست.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            gregorian = self.current_jdate.togregorian()
            date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
            self.db.delete_all_deleted_tasks(date_str)
            self.load_deleted_tasks()
            QMessageBox.information(self, "تسک‌های حذف شده", "✅ همه تسک‌های حذف شده پاک شدند.")

    def on_task_deleted(self, task_id, task_text):
        gregorian = self.current_jdate.togregorian()
        date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
        self.db.move_to_deleted(task_id, task_text, date_str)
        self.load_tasks()
        self.load_deleted_tasks()

    def on_task_toggled(self, task_id, new_status):
        self.db.toggle_status(task_id, 1 if new_status else 0)
        self.load_tasks()

    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            import jdatetime
            today = jdatetime.date.today()
            if self.current_jdate < today:
                QMessageBox.warning(self, "خطا", "امکان اضافه کردن تسک برای روزهای گذشته وجود ندارد!\nفقط می‌توانید برای امروز و روزهای آینده تسک اضافه کنید.")
                return
            gregorian = self.current_jdate.togregorian()
            date_str = f"{gregorian.year}-{gregorian.month:02d}-{gregorian.day:02d}"
            self.db.add_task(date_str, text)
            self.load_tasks()
            self.task_input.clear()
            self.calendar_widget.load_task_dates()
            self.calendar_widget.update_calendar()

    def start_clock(self):
        self.update_clock()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

    def update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def start_move(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
            self.dragging = True

    def do_move(self, event):
        if self.dragging and self.drag_pos:
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()

    def stop_move(self, event):
        self.dragging = False
        self.drag_pos = None

    def close_app(self):
        self.db.close()
        self.tray_icon.hide()
        self.close()
        QApplication.quit()


if __name__ == "__main__":
    # Qt باید DPI scaling ویندوز رو خودش هندل کنه
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    # مقداردهی اسکیل بعد از ساخت QApplication
    _SCALE = get_scale_factor()
    window = MainWidget()
    window.show()
    sys.exit(app.exec())