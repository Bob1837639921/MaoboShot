from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QStyle, QApplication
from PySide6.QtGui import QIcon, QAction
from core.config import ICON_PATH

class ManboShotTrayIcon(QSystemTrayIcon):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setToolTip("✨ ManboShot")
        
        icon_file = ICON_PATH / "icon.ico"
        if icon_file.exists():
            self.setIcon(QIcon(str(icon_file)))
        else:
            self.setIcon(self.window.style().standardIcon(QStyle.SP_ComputerIcon))
            
        self.activated.connect(self.on_tray_icon_activated)
        self.setup_menu()
        self.show()

    def setup_menu(self):
        self.tray_menu = QMenu()
        
        show_action = QAction("显示主界面 (Alt+Q)", self)
        show_action.triggered.connect(lambda: self.window.handle_show_window(reset=True))
        
        snip_action = QAction("截图翻译 (Alt+Z)", self)
        snip_action.triggered.connect(self.window.start_snipping)
        
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.window.show_settings)
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_menu.addAction(show_action)
        self.tray_menu.addAction(snip_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(settings_action)
        self.tray_menu.addAction(quit_action)
        
        self.setContextMenu(self.tray_menu)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.window.handle_show_window(reset=True)
