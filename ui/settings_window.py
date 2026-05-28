from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox, QComboBox)
from PySide6.QtCore import Qt
from core.config import load_app_config, save_app_config

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置 - ManboShot")
        self.setFixedSize(520, 620)
        self.setAttribute(Qt.WA_StyledBackground, True)
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

        # 语音引擎选择
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["☁️ 纯云端语音 (发音纯正/依赖网络)", "⚡ 混合语音 (短文本极速本地响应)"])
        
        tts_layout = QVBoxLayout()
        tts_layout.setSpacing(5)
        tts_layout.addWidget(QLabel("🔊 语音合成引擎:"))
        tts_layout.addWidget(self.tts_combo)
        layout.addLayout(tts_layout)

        # AI 语音设置
        self.ai_tts_provider_combo = QComboBox()
        self.ai_tts_provider_combo.addItems(["Edge TTS", "小米 MiMo TTS"])
        ai_provider_layout = QVBoxLayout()
        ai_provider_layout.setSpacing(5)
        ai_provider_layout.addWidget(QLabel("🤖 AI 语音提供商:"))
        ai_provider_layout.addWidget(self.ai_tts_provider_combo)
        layout.addLayout(ai_provider_layout)

        self.xiaomi_key_input = QLineEdit()
        self.xiaomi_key_input.setEchoMode(QLineEdit.Password)
        self.xiaomi_key_input.setPlaceholderText("小米 MiMo / 网关 API Key")

        xiaomi_key_layout = QVBoxLayout()
        xiaomi_key_layout.setSpacing(5)
        xiaomi_key_layout.addWidget(QLabel("🔑 小米 TTS API Key:"))
        xiaomi_key_layout.addWidget(self.xiaomi_key_input)
        layout.addLayout(xiaomi_key_layout)

        self.xiaomi_base_input = QLineEdit()
        self.xiaomi_base_input.setPlaceholderText("https://token-plan-cn.xiaomimimo.com/v1")

        xiaomi_base_layout = QVBoxLayout()
        xiaomi_base_layout.setSpacing(5)
        xiaomi_base_layout.addWidget(QLabel("🌐 小米 TTS Base URL:"))
        xiaomi_base_layout.addWidget(self.xiaomi_base_input)
        layout.addLayout(xiaomi_base_layout)

        xiaomi_model_voice_layout = QHBoxLayout()
        self.xiaomi_model_input = QLineEdit()
        self.xiaomi_model_input.setPlaceholderText("mimo-v2-tts")
        self.xiaomi_voice_combo = QComboBox()
        self.xiaomi_voice_combo.addItems(["mimo_default", "default_zh", "default_en"])

        model_layout = QVBoxLayout()
        model_layout.setSpacing(5)
        model_layout.addWidget(QLabel("🧠 小米 TTS 模型:"))
        model_layout.addWidget(self.xiaomi_model_input)

        voice_layout = QVBoxLayout()
        voice_layout.setSpacing(5)
        voice_layout.addWidget(QLabel("🎙️ 小米 TTS 音色:"))
        voice_layout.addWidget(self.xiaomi_voice_combo)

        xiaomi_model_voice_layout.addLayout(model_layout)
        xiaomi_model_voice_layout.addLayout(voice_layout)
        layout.addLayout(xiaomi_model_voice_layout)

        self.xiaomi_style_input = QLineEdit()
        self.xiaomi_style_input.setPlaceholderText("可选：开心 / 粤语 / 东北话 / 变慢 / 悄悄话")

        xiaomi_style_layout = QVBoxLayout()
        xiaomi_style_layout.setSpacing(5)
        xiaomi_style_layout.addWidget(QLabel("🎭 小米 TTS 风格:"))
        xiaomi_style_layout.addWidget(self.xiaomi_style_input)
        layout.addLayout(xiaomi_style_layout)

        # 播放器引擎选择
        self.player_combo = QComboBox()
        self.player_combo.addItems(["pygame (默认)", "mpv (增强音质)"])
        self.player_combo.currentIndexChanged.connect(self._on_player_changed)
        
        player_layout = QVBoxLayout()
        player_layout.setSpacing(5)
        player_layout.addWidget(QLabel("🎵 音频播放引擎:"))
        player_layout.addWidget(self.player_combo)
        layout.addLayout(player_layout)

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

    def _on_player_changed(self, index):
        if index == 1:
            from core.config import MPV_EXE, TOOL_DIR
            if not MPV_EXE.exists():
                QMessageBox.warning(self, "缺少 mpv", 
                                    f"未检测到 mpv.exe。\n\n如需使用 mpv 播放器，请下载 Windows 版本的 mpv，并将解压后的 mpv.exe 放置在以下目录中：\n{TOOL_DIR}\n\n下载地址：https://mpv.io/installation/")
                self.player_combo.setCurrentIndex(0)

    def _load_current(self):
        config = load_app_config()
        self.key_input.setText(config.get("DOUBAO_API_KEY", ""))
        self.ep_input.setText(config.get("DOUBAO_MODEL_EP", ""))
        
        use_local_tts = config.get("USE_LOCAL_TTS", True)
        if use_local_tts:
            self.tts_combo.setCurrentIndex(1)
        else:
            self.tts_combo.setCurrentIndex(0)

        ai_tts_provider = config.get("AI_TTS_PROVIDER", "edge")
        self.ai_tts_provider_combo.setCurrentIndex(1 if ai_tts_provider == "xiaomi" else 0)
        self.xiaomi_key_input.setText(config.get("XIAOMI_TTS_API_KEY", ""))
        self.xiaomi_base_input.setText(config.get("XIAOMI_TTS_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"))
        self.xiaomi_model_input.setText(config.get("XIAOMI_TTS_MODEL", "mimo-v2-tts"))
        voice = config.get("XIAOMI_TTS_VOICE", "mimo_default")
        voice_index = self.xiaomi_voice_combo.findText(voice)
        self.xiaomi_voice_combo.setCurrentIndex(voice_index if voice_index >= 0 else 0)
        self.xiaomi_style_input.setText(config.get("XIAOMI_TTS_STYLE", ""))
        
        player_engine = config.get("AUDIO_PLAYER", "pygame")
        self.player_combo.setCurrentIndex(1 if player_engine == "mpv" else 0)
            
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
        use_local_tts_val = (self.tts_combo.currentIndex() == 1)
        ai_tts_provider = "xiaomi" if self.ai_tts_provider_combo.currentIndex() == 1 else "edge"
        new_config = {
            "DOUBAO_API_KEY": self.key_input.text().strip(),
            "DOUBAO_MODEL_EP": self.ep_input.text().strip(),
            "THEME": theme_val,
            "USE_LOCAL_TTS": use_local_tts_val,
            "AI_TTS_PROVIDER": ai_tts_provider,
            "XIAOMI_TTS_API_KEY": self.xiaomi_key_input.text().strip(),
            "XIAOMI_TTS_BASE_URL": self.xiaomi_base_input.text().strip() or "https://token-plan-cn.xiaomimimo.com/v1",
            "XIAOMI_TTS_MODEL": self.xiaomi_model_input.text().strip() or "mimo-v2-tts",
            "XIAOMI_TTS_VOICE": self.xiaomi_voice_combo.currentText(),
            "XIAOMI_TTS_STYLE": self.xiaomi_style_input.text().strip(),
            "AUDIO_PLAYER": "mpv" if self.player_combo.currentIndex() == 1 else "pygame"
        }
        save_app_config(new_config)
        QMessageBox.information(self, "成功", "设置已保存，立即生效！")
        self.accept()
