from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox, QComboBox,
                               QListWidget, QListWidgetItem, QStackedWidget, QWidget, QFrame, QScrollArea)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from core.config import load_app_config, save_app_config, ICON_PATH

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置 - ManboShot")
        self.setFixedSize(750, 580)
        
        icon_file = ICON_PATH / "icon.ico"
        if icon_file.exists():
            self.setWindowIcon(QIcon(str(icon_file)))
            
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.init_ui()
        self._load_current()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ================= Sidebar =================
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        self.sidebar.setFocusPolicy(Qt.NoFocus)
        self.sidebar.currentRowChanged.connect(self.change_page)

        items = ["🤖 AI 翻译模型", "🔊 语音与 TTS", "⚙️ 通用与外观"]
        for item_text in items:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(200, 50))
            self.sidebar.addItem(item)

        # ================= Right Content Area =================
        self.right_widget = QWidget()
        self.right_widget.setObjectName("rightWidget")
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(30, 30, 30, 20)
        right_layout.setSpacing(20)

        self.stacked_widget = QStackedWidget()
        
        self.page_ai = self.create_ai_page()
        self.page_tts = self.create_tts_page()
        self.page_general = self.create_general_page()

        self.stacked_widget.addWidget(self.page_ai)
        self.stacked_widget.addWidget(self.page_tts)
        self.stacked_widget.addWidget(self.page_general)

        # ================= Bottom Buttons =================
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)

        right_layout.addWidget(self.stacked_widget)
        right_layout.addLayout(btn_layout)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.right_widget)

        self.sidebar.setCurrentRow(0)

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def create_card(self, title, description, inner_layout):
        card = QFrame()
        card.setProperty("class", "settings-card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "card-title")
        header_layout.addWidget(title_lbl)
        
        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setProperty("class", "card-desc")
            desc_lbl.setWordWrap(True)
            header_layout.addWidget(desc_lbl)
        
        card_layout.addLayout(header_layout)
        
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setProperty("class", "card-divider")
        card_layout.addWidget(divider)
        
        card_layout.addLayout(inner_layout)
        return card

    def create_ai_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Doubao Card
        v_layout = QVBoxLayout()
        v_layout.setSpacing(10)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("例如: sk-xxxxxxxx...")
        
        key_label = QLabel("API Key")
        key_label.setProperty("class", "input-label")
        v_layout.addWidget(key_label)
        v_layout.addWidget(self.key_input)

        self.ep_input = QLineEdit()
        self.ep_input.setPlaceholderText("例如: ep-2024xxxxxx-xxxxx 或 gpt-4o")
        
        ep_label = QLabel("模型名称或接入点 (Model)")
        ep_label.setProperty("class", "input-label")
        v_layout.addWidget(ep_label)
        v_layout.addWidget(self.ep_input)
        
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("例如: https://ark.cn-beijing.volces.com/api/v3")
        
        base_url_label = QLabel("API Base URL")
        base_url_label.setProperty("class", "input-label")
        v_layout.addWidget(base_url_label)
        v_layout.addWidget(self.base_url_input)

        card = self.create_card(
            "AI 大模型配置 (兼容 OpenAI 格式)", 
            "填写配置以启用高级AI翻译。如果留空，系统将默认回退到基础的 Google 纯享翻译模式。", 
            v_layout
        )
        layout.addWidget(card)
        layout.addStretch()
        return page

    def create_tts_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Engine Card
        engine_layout = QVBoxLayout()
        engine_layout.setSpacing(10)
        
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["☁️ 纯云端语音 (发音纯正/依赖网络)", "⚡ 混合语音 (短文本极速本地响应)"])
        
        tts_label = QLabel("引擎工作模式")
        tts_label.setProperty("class", "input-label")
        engine_layout.addWidget(tts_label)
        engine_layout.addWidget(self.tts_combo)
        
        self.ai_tts_provider_combo = QComboBox()
        self.ai_tts_provider_combo.addItems(["Edge TTS (免费/稳定)", "小米 MiMo TTS (高级)"])
        
        provider_label = QLabel("云端 AI 提供商")
        provider_label.setProperty("class", "input-label")
        engine_layout.addWidget(provider_label)
        engine_layout.addWidget(self.ai_tts_provider_combo)

        engine_card = self.create_card("语音引擎设置", "配置文本朗读的基础行为和提供商。", engine_layout)
        layout.addWidget(engine_card)

        # Xiaomi Card
        xiaomi_layout = QVBoxLayout()
        xiaomi_layout.setSpacing(10)

        self.xiaomi_key_input = QLineEdit()
        self.xiaomi_key_input.setEchoMode(QLineEdit.Password)
        self.xiaomi_key_input.setPlaceholderText("填写 API Key")
        
        x_key_lbl = QLabel("API Key")
        x_key_lbl.setProperty("class", "input-label")
        xiaomi_layout.addWidget(x_key_lbl)
        xiaomi_layout.addWidget(self.xiaomi_key_input)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(15)
        
        col1 = QVBoxLayout()
        self.xiaomi_model_input = QLineEdit()
        self.xiaomi_model_input.setPlaceholderText("mimo-v2-tts")
        m_lbl = QLabel("模型")
        m_lbl.setProperty("class", "input-label")
        col1.addWidget(m_lbl)
        col1.addWidget(self.xiaomi_model_input)
        
        col2 = QVBoxLayout()
        self.xiaomi_voice_combo = QComboBox()
        self.xiaomi_voice_combo.addItems(["mimo_default", "default_zh", "default_en"])
        v_lbl = QLabel("音色")
        v_lbl.setProperty("class", "input-label")
        col2.addWidget(v_lbl)
        col2.addWidget(self.xiaomi_voice_combo)
        
        row_layout.addLayout(col1)
        row_layout.addLayout(col2)
        xiaomi_layout.addLayout(row_layout)

        self.xiaomi_base_input = QLineEdit()
        self.xiaomi_base_input.setPlaceholderText("https://token-plan-cn.xiaomimimo.com/v1")
        b_lbl = QLabel("Base URL")
        b_lbl.setProperty("class", "input-label")
        xiaomi_layout.addWidget(b_lbl)
        xiaomi_layout.addWidget(self.xiaomi_base_input)

        self.xiaomi_style_input = QLineEdit()
        self.xiaomi_style_input.setPlaceholderText("可选：开心 / 粤语 / 东北话 / 变慢")
        s_lbl = QLabel("特殊风格 (Style)")
        s_lbl.setProperty("class", "input-label")
        xiaomi_layout.addWidget(s_lbl)
        xiaomi_layout.addWidget(self.xiaomi_style_input)

        xiaomi_card = self.create_card("小米 MiMo 专属配置", "仅当上方提供商选择小米 MiMo 时生效。", xiaomi_layout)
        
        # 使用 ScrollArea 包裹 TTS 页面以防高度超限
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")
        
        inner_widget = QWidget()
        inner_widget.setStyleSheet("QWidget { background-color: transparent; }")
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.addWidget(engine_card)
        inner_layout.addWidget(xiaomi_card)
        inner_layout.addStretch()
        
        scroll_area.setWidget(inner_widget)
        layout.addWidget(scroll_area)
        return page

    def create_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # General Card
        g_layout = QVBoxLayout()
        g_layout.setSpacing(10)

        self.player_combo = QComboBox()
        self.player_combo.addItems(["pygame (默认/兼容性极佳)", "mpv (增强音质/需额外下载)"])
        self.player_combo.currentIndexChanged.connect(self._on_player_changed)
        p_lbl = QLabel("音频播放底层驱动")
        p_lbl.setProperty("class", "input-label")
        g_layout.addWidget(p_lbl)
        g_layout.addWidget(self.player_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["🌙 暗色主题 (Dark Mode)", "☀️ 浅色主题 (Light Mode)"])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme_from_combo)
        t_lbl = QLabel("应用外观风格")
        t_lbl.setProperty("class", "input-label")
        g_layout.addWidget(t_lbl)
        g_layout.addWidget(self.theme_combo)

        card = self.create_card("通用与外观", "调整应用程序的基础行为和视觉体验。", g_layout)
        layout.addWidget(card)
        layout.addStretch()
        return page

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
        self.base_url_input.setText(config.get("AI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))
        
        use_local_tts = config.get("USE_LOCAL_TTS", True)
        self.tts_combo.setCurrentIndex(1 if use_local_tts else 0)

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
        self.theme_combo.setCurrentIndex(1 if theme == "light" else 0)
        
        # Apply theme immediately on load
        self.apply_theme_from_combo(self.theme_combo.currentIndex())

    def apply_theme_from_combo(self, index):
        is_light = (index == 1)
        
        if is_light:
            bg_main = "#f4f5f7"
            bg_sidebar = "#e9eaed"
            bg_card = "#ffffff"
            text_main = "#172b4d"
            text_desc = "#5e6c84"
            border_col = "#dfe1e6"
            input_bg = "#fafbfc"
            input_border = "#dfe1e6"
            list_hover = "#dce0e5"
            list_selected = "#ffffff"
            list_sel_text = "#0052cc"
            btn_bg = "#f4f5f7"
            btn_hover = "#ebecf0"
            btn_text = "#42526e"
            primary_bg = "#0052cc"
            primary_hover = "#0065ff"
            divider_col = "#ebecf0"
        else:
            bg_main = "#1e1e1e"
            bg_sidebar = "#252526"
            bg_card = "#2d2d2d"
            text_main = "#ffffff"
            text_desc = "#aaaaaa"
            border_col = "#3e3e42"
            input_bg = "#3c3c3c"
            input_border = "#555555"
            list_hover = "#2a2d2e"
            list_selected = "#37373d"
            list_sel_text = "#ffffff"
            btn_bg = "#3a3a3a"
            btn_hover = "#4a4a4a"
            btn_text = "#ffffff"
            primary_bg = "#0e639c"
            primary_hover = "#1177bb"
            divider_col = "#3e3e42"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_main};
                color: {text_main};
                font-family: 'Segoe UI', 'Microsoft YaHei';
            }}
            
            /* Sidebar styling */
            QListWidget#sidebar {{
                background-color: {bg_sidebar};
                border: none;
                border-right: 1px solid {border_col};
                outline: none;
                padding-top: 15px;
            }}
            QListWidget#sidebar::item {{
                color: {text_main};
                padding: 10px 20px;
                margin: 5px 10px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }}
            QListWidget#sidebar::item:hover {{
                background-color: {list_hover};
            }}
            QListWidget#sidebar::item:selected {{
                background-color: {list_selected};
                color: {list_sel_text};
                font-weight: bold;
                border: 1px solid {border_col};
            }}
            
            /* Right Area */
            QWidget#rightWidget {{
                background-color: {bg_main};
            }}

            /* Card styling */
            QFrame.settings-card {{
                background-color: {bg_card};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
            QLabel.card-title {{
                color: {text_main};
                font-size: 16px;
                font-weight: bold;
            }}
            QLabel.card-desc {{
                color: {text_desc};
                font-size: 12px;
            }}
            QFrame.card-divider {{
                background-color: {divider_col};
                max-height: 1px;
                border: none;
                margin: 5px 0;
            }}

            /* Input styling */
            QLabel.input-label {{
                color: {text_main};
                font-size: 13px;
                font-weight: 500;
            }}
            QLineEdit, QComboBox {{
                background-color: {input_bg};
                color: {text_main};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {primary_bg};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none; /* Can add a custom arrow icon if desired */
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {text_desc};
                margin-right: 10px;
            }}
            
            /* Button styling */
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
            QPushButton#saveBtn {{
                background-color: {primary_bg};
                color: white;
                border: none;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {primary_hover};
            }}
            
            /* ScrollBar */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {text_desc};
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
        """)

    def save_settings(self):
        theme_val = "light" if self.theme_combo.currentIndex() == 1 else "dark"
        use_local_tts_val = (self.tts_combo.currentIndex() == 1)
        ai_tts_provider = "xiaomi" if self.ai_tts_provider_combo.currentIndex() == 1 else "edge"
        new_config = {
            "DOUBAO_API_KEY": self.key_input.text().strip(),
            "DOUBAO_MODEL_EP": self.ep_input.text().strip(),
            "AI_BASE_URL": self.base_url_input.text().strip(),
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
