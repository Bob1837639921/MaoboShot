from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox, QComboBox)
from PySide6.QtCore import Qt
from core.config import load_app_config, save_app_config

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置 - ManboShot")
        self.setFixedSize(450, 280)
        # 去掉无边框，允许普通窗口操作，但置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; font-family: 'Segoe UI', 'Microsoft YaHei'; }
            QLabel { color: #e0e0e0; font-size: 13px; font-weight: bold; }
            QLineEdit { background-color: #3a3a3a; color: #ffffff; border: 1px solid #555; border-radius: 5px; padding: 6px; }
            QLineEdit:focus { border: 1px solid #1a73e8; }
            QPushButton { background-color: #555; color: white; border: none; border-radius: 5px; padding: 6px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #666; }
            QPushButton#saveBtn { background-color: #1a73e8; }
            QPushButton#saveBtn:hover { background-color: #2b84f3; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 提示信息
        info_label = QLabel("✨ 填写火山引擎(豆包)配置启用AI功能，留空则默认纯Google模式。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #aaaaaa; font-weight: normal; margin-bottom: 5px;")
        layout.addWidget(info_label)

        # API Key
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("例如: d3b9xxxx-xxxx-xxxx...")
        
        key_layout = QVBoxLayout()
        key_layout.setSpacing(5)
        key_layout.addWidget(QLabel("🔑 Doubao API Key:"))
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)

        # Endpoint
        self.ep_input = QLineEdit()
        self.ep_input.setPlaceholderText("例如: ep-2024xxxxxx-xxxxx")
        
        ep_layout = QVBoxLayout()
        ep_layout.setSpacing(5)
        ep_layout.addWidget(QLabel("🔌 接入点 (Model Endpoint):"))
        ep_layout.addWidget(self.ep_input)
        layout.addLayout(ep_layout)

        # 主题选择
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["🌙 暗色主题 (Dark)", "☀️ 浅色主题 (Light)"])
        
        theme_layout = QVBoxLayout()
        theme_layout.setSpacing(5)
        theme_layout.addWidget(QLabel("🎨 界面主题:"))
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存配置")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

        self._load_current()

    def _load_current(self):
        config = load_app_config()
        self.key_input.setText(config.get("DOUBAO_API_KEY", ""))
        self.ep_input.setText(config.get("DOUBAO_MODEL_EP", ""))
        
        theme = config.get("THEME", "dark")
        if hasattr(self, 'theme_combo'):
            if theme == "light":
                self.theme_combo.setCurrentIndex(1)
                self.setStyleSheet("""
                    QDialog { background-color: #f5f5f5; color: #333333; font-family: 'Segoe UI', 'Microsoft YaHei'; }
                    QLabel { color: #333333; font-size: 13px; font-weight: bold; }
                    QLineEdit { background-color: #ffffff; color: #333333; border: 1px solid #ccc; border-radius: 5px; padding: 6px; }
                    QLineEdit:focus { border: 1px solid #1a73e8; }
                    QPushButton { background-color: #e0e0e0; color: #333; border: none; border-radius: 5px; padding: 6px 15px; font-weight: bold; }
                    QPushButton:hover { background-color: #d0d0d0; }
                    QPushButton#saveBtn { background-color: #1a73e8; color: white; }
                    QPushButton#saveBtn:hover { background-color: #2b84f3; }
                    QComboBox { background-color: #ffffff; color: #333333; border: 1px solid #ccc; border-radius: 5px; padding: 5px; }
                """)
            else:
                self.theme_combo.setCurrentIndex(0)
                self.setStyleSheet("""
                    QDialog { background-color: #2b2b2b; color: #ffffff; font-family: 'Segoe UI', 'Microsoft YaHei'; }
                    QLabel { color: #e0e0e0; font-size: 13px; font-weight: bold; }
                    QLineEdit { background-color: #3a3a3a; color: #ffffff; border: 1px solid #555; border-radius: 5px; padding: 6px; }
                    QLineEdit:focus { border: 1px solid #1a73e8; }
                    QPushButton { background-color: #555; color: white; border: none; border-radius: 5px; padding: 6px 15px; font-weight: bold; }
                    QPushButton:hover { background-color: #666; }
                    QPushButton#saveBtn { background-color: #1a73e8; color: white; }
                    QPushButton#saveBtn:hover { background-color: #2b84f3; }
                    QComboBox { background-color: #3a3a3a; color: #ffffff; border: 1px solid #555; border-radius: 5px; padding: 5px; }
                """)

    def save_settings(self):
        theme_val = "light" if (hasattr(self, 'theme_combo') and self.theme_combo.currentIndex() == 1) else "dark"
        new_config = {
            "DOUBAO_API_KEY": self.key_input.text().strip(),
            "DOUBAO_MODEL_EP": self.ep_input.text().strip(),
            "THEME": theme_val
        }
        save_app_config(new_config)
        QMessageBox.information(self, "成功", "设置已保存，立即生效！")
        self.accept()
