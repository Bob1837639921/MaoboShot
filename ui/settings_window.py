from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QTextEdit, QPushButton, QMessageBox, QComboBox,
                               QListWidget, QListWidgetItem, QStackedWidget, QWidget, QFrame, QScrollArea,
                               QKeySequenceEdit, QCheckBox, QSlider)
from PySide6.QtCore import QRectF, Qt, QSize
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPainterPath, QPixmap
from core.config import load_app_config, save_app_config, ICON_PATH
from core.pet_pack import discover_pet_packs
from ui.theme import (
    THEME_LABELS,
    THEME_ORDER,
    normalize_theme,
    theme_palette,
    theme_texture_path,
)


THEME_TOOLTIPS = {
    "dark": "低亮度经典界面，适合夜间使用",
    "light": "清爽明亮的经典界面",
    "graphite": "深色等高线纹理与青蓝强调色",
    "blueprint": "冰霜玻璃质感与蓝图纹理",
    "signal": "深色电路纹理与青橙信号色",
}


class ClearArrowComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow_color = QColor("#6B7280")

    def set_arrow_color(self, color):
        self._arrow_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self._arrow_color)
        font = painter.font()
        font.setFamily("Segoe UI Symbol")
        font.setPixelSize(15)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.width() - 39,
            0,
            38,
            self.height(),
            Qt.AlignCenter,
            "▾",
        )


def create_theme_preview(theme_name):
    palette = theme_palette(theme_name)
    preview = QPixmap(52, 22)
    preview.fill(Qt.transparent)

    painter = QPainter(preview)
    painter.setRenderHint(QPainter.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0.5, 0.5, 51, 21), 4, 4)
    painter.setClipPath(clip)

    texture_path = theme_texture_path(theme_name)
    if texture_path:
        texture = QPixmap(str(texture_path)).scaled(
            preview.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        x = (preview.width() - texture.width()) // 2
        y = (preview.height() - texture.height()) // 2
        painter.drawPixmap(x, y, texture)
    else:
        painter.fillRect(preview.rect(), QColor(palette["surface"]))
        painter.fillRect(0, 0, 18, 17, QColor(palette["surface_subtle"]))

    accent_y = preview.height() - 5
    painter.fillRect(0, accent_y, 18, 5, QColor(palette["primary"]))
    painter.fillRect(18, accent_y, 17, 5, QColor(palette["ai_accent"]))
    painter.fillRect(35, accent_y, 17, 5, QColor(palette["google_accent"]))
    painter.setClipping(False)
    painter.setPen(QColor(palette["border"]))
    painter.drawRoundedRect(QRectF(0.5, 0.5, 51, 21), 4, 4)
    painter.end()
    return preview


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 · ManboShot")
        self.setFixedSize(820, 620)
        
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
        self.sidebar_panel = QFrame()
        self.sidebar_panel.setObjectName("sidebarPanel")
        self.sidebar_panel.setFixedWidth(190)
        sidebar_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_layout.setContentsMargins(14, 24, 14, 18)
        sidebar_layout.setSpacing(2)

        self.sidebar_brand = QLabel("ManboShot")
        self.sidebar_brand.setObjectName("sidebarBrand")
        self.sidebar_caption = QLabel("偏好设置")
        self.sidebar_caption.setObjectName("sidebarCaption")

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFocusPolicy(Qt.NoFocus)
        self.sidebar.currentRowChanged.connect(self.change_page)

        items = ["AI 翻译", "语音与 TTS", "桌面宠物", "通用设置"]
        for item_text in items:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(150, 44))
            self.sidebar.addItem(item)

        sidebar_layout.addWidget(self.sidebar_brand)
        sidebar_layout.addWidget(self.sidebar_caption)
        sidebar_layout.addSpacing(22)
        sidebar_layout.addWidget(self.sidebar)

        # ================= Right Content Area =================
        self.right_widget = QWidget()
        self.right_widget.setObjectName("rightWidget")
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(28, 24, 28, 20)
        right_layout.setSpacing(16)

        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_description = QLabel()
        self.page_description.setObjectName("pageDescription")

        self.stacked_widget = QStackedWidget()
        
        self.page_ai = self.create_ai_page()
        self.page_tts = self.create_tts_page()
        self.page_pet = self.create_pet_page()
        self.page_general = self.create_general_page()

        self.stacked_widget.addWidget(self.page_ai)
        self.stacked_widget.addWidget(self.page_tts)
        self.stacked_widget.addWidget(self.page_pet)
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

        right_layout.addWidget(self.page_title)
        right_layout.addWidget(self.page_description)
        right_layout.addWidget(self.stacked_widget)
        right_layout.addLayout(btn_layout)

        main_layout.addWidget(self.sidebar_panel)
        main_layout.addWidget(self.right_widget)

        self.sidebar.setCurrentRow(0)

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        titles = ["AI 翻译", "语音与 TTS", "桌面宠物", "通用设置"]
        descriptions = [
            "连接兼容 OpenAI 格式的模型服务",
            "选择朗读引擎、服务商与声音风格",
            "管理桌面伙伴、结果气泡与角色资源",
            "管理外观、快捷键与音频播放方式",
        ]
        if 0 <= index < len(titles):
            self.page_title.setText(titles[index])
            self.page_description.setText(descriptions[index])

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
        
        self.tts_combo = ClearArrowComboBox()
        self.tts_combo.addItems(["☁️ 纯云端语音 (发音纯正/依赖网络)", "⚡ 混合语音 (短文本极速本地响应)"])
        
        tts_label = QLabel("引擎工作模式")
        tts_label.setProperty("class", "input-label")
        engine_layout.addWidget(tts_label)
        engine_layout.addWidget(self.tts_combo)
        
        self.ai_tts_provider_combo = ClearArrowComboBox()
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
        self.xiaomi_model_input.setPlaceholderText("mimo-v2.5-tts")
        m_lbl = QLabel("模型")
        m_lbl.setProperty("class", "input-label")
        col1.addWidget(m_lbl)
        col1.addWidget(self.xiaomi_model_input)
        
        col2 = QVBoxLayout()
        self.xiaomi_voice_combo = ClearArrowComboBox()
        self.xiaomi_voice_combo.addItems(["mimo_default", "冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean"])
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

        self.xiaomi_style_input = QTextEdit()
        self.xiaomi_style_input.setFixedHeight(72)
        self.xiaomi_style_input.setAcceptRichText(False)
        self.xiaomi_style_input.setPlaceholderText("例如：温柔、东北话、(粤语)、用轻快上扬的语调朗读")
        s_lbl = QLabel("特殊风格 (Style)")
        s_lbl.setProperty("class", "input-label")
        xiaomi_layout.addWidget(s_lbl)
        xiaomi_layout.addWidget(self.xiaomi_style_input)
        style_hint = QLabel(
            "风格示例：开心/悲伤/愤怒/平静/冷漠；温柔/高冷/活泼/严肃/慵懒；"
            "磁性/清亮/甜美/沙哑；夹子音/御姐音/正太音/大叔音；"
            "东北话/四川话/河南话/粤语；孙悟空/林黛玉；(唱歌)"
        )
        style_hint.setProperty("class", "card-desc")
        style_hint.setWordWrap(True)
        xiaomi_layout.addWidget(style_hint)

        xiaomi_card = self.create_card("小米 MiMo 专属配置", "仅当上方提供商选择小米 MiMo 时生效。", xiaomi_layout)
        
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

        self.player_combo = ClearArrowComboBox()
        self.player_combo.addItems(["pygame (默认/兼容性极佳)", "mpv (增强音质/需额外下载)"])
        self.player_combo.currentIndexChanged.connect(self._on_player_changed)
        p_lbl = QLabel("音频播放底层驱动")
        p_lbl.setProperty("class", "input-label")
        g_layout.addWidget(p_lbl)
        g_layout.addWidget(self.player_combo)

        self.theme_combo = ClearArrowComboBox()
        self.theme_combo.setIconSize(QSize(52, 22))
        self.theme_combo.setMinimumHeight(42)
        for theme_name in THEME_ORDER:
            self.theme_combo.addItem(
                QIcon(create_theme_preview(theme_name)),
                THEME_LABELS[theme_name],
                theme_name,
            )
            item_index = self.theme_combo.count() - 1
            self.theme_combo.setItemData(
                item_index, THEME_TOOLTIPS[theme_name], Qt.ToolTipRole
            )
        self.theme_combo.currentIndexChanged.connect(self.apply_theme_from_combo)
        t_lbl = QLabel("应用外观风格")
        t_lbl.setProperty("class", "input-label")
        g_layout.addWidget(t_lbl)
        g_layout.addWidget(self.theme_combo)

        # 快捷键配置区域
        self.hotkey_show_edit = QKeySequenceEdit()
        self.hotkey_show_edit.setToolTip("按键盘键组合设置唤醒热键")
        show_lbl = QLabel("唤醒主界面快捷键")
        show_lbl.setProperty("class", "input-label")
        g_layout.addWidget(show_lbl)
        g_layout.addWidget(self.hotkey_show_edit)

        self.hotkey_snip_edit = QKeySequenceEdit()
        self.hotkey_snip_edit.setToolTip("按键盘键组合设置截图翻译热键")
        snip_lbl = QLabel("截图翻译快捷键")
        snip_lbl.setProperty("class", "input-label")
        g_layout.addWidget(snip_lbl)
        g_layout.addWidget(self.hotkey_snip_edit)

        card = self.create_card("通用与外观", "调整应用程序的基础行为和视觉体验。", g_layout)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def create_pet_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        pet_layout = QVBoxLayout()
        pet_layout.setSpacing(12)

        self.pet_enabled_check = QCheckBox("在桌面显示宠物")
        self.pet_enabled_check.setToolTip("关闭后可从托盘菜单重新开启")
        pet_layout.addWidget(self.pet_enabled_check)

        pet_lbl = QLabel("选择桌面伙伴")
        pet_lbl.setProperty("class", "input-label")
        self.pet_combo = ClearArrowComboBox()
        self.pet_combo.setMinimumHeight(42)
        for pack in discover_pet_packs():
            self.pet_combo.addItem(pack.name, pack.pet_id)
        pet_layout.addWidget(pet_lbl)
        pet_layout.addWidget(self.pet_combo)

        self.pet_bubble_check = QCheckBox("翻译时显示结果气泡")
        self.pet_bubble_check.setToolTip("主翻译窗口仍保留完整的双引擎结果")
        pet_layout.addWidget(self.pet_bubble_check)

        scale_header = QHBoxLayout()
        scale_lbl = QLabel("宠物大小")
        scale_lbl.setProperty("class", "input-label")
        self.pet_scale_value = QLabel("100%")
        self.pet_scale_value.setProperty("class", "card-desc")
        scale_header.addWidget(scale_lbl)
        scale_header.addStretch()
        scale_header.addWidget(self.pet_scale_value)
        self.pet_scale_slider = QSlider(Qt.Horizontal)
        self.pet_scale_slider.setRange(70, 140)
        self.pet_scale_slider.setSingleStep(5)
        self.pet_scale_slider.setPageStep(10)
        self.pet_scale_slider.setTickInterval(10)
        self.pet_scale_slider.valueChanged.connect(
            lambda value: self.pet_scale_value.setText(f"{value}%")
        )
        pet_layout.addLayout(scale_header)
        pet_layout.addWidget(self.pet_scale_slider)

        hint = QLabel("双击宠物打开翻译窗口；拖动可跨屏摆放；右键可快速管理。")
        hint.setProperty("class", "card-desc")
        hint.setWordWrap(True)
        pet_layout.addWidget(hint)

        card = self.create_card(
            "桌面伙伴",
            "宠物动作会跟随识图、翻译、失败与朗读状态变化。角色采用独立资源包，可随时替换。",
            pet_layout,
        )
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
        xiaomi_base_url = config.get("XIAOMI_TTS_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
        self.xiaomi_base_input.setText(xiaomi_base_url)
        xiaomi_model = config.get("XIAOMI_TTS_MODEL", "mimo-v2.5-tts")
        if xiaomi_model == "mimo-v2-tts":
            xiaomi_model = "mimo-v2.5-tts"
        self.xiaomi_model_input.setText(xiaomi_model)
        voice = config.get("XIAOMI_TTS_VOICE", "mimo_default")
        voice_index = self.xiaomi_voice_combo.findText(voice)
        self.xiaomi_voice_combo.setCurrentIndex(voice_index if voice_index >= 0 else 0)
        self.xiaomi_style_input.setPlainText(config.get("XIAOMI_TTS_STYLE", ""))
        
        player_engine = config.get("AUDIO_PLAYER", "pygame")
        self.player_combo.setCurrentIndex(1 if player_engine == "mpv" else 0)
            
        theme = normalize_theme(config.get("THEME", "dark"))
        theme_index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        
        # 加载快捷键
        show_hk = config.get("HOTKEY_SHOW", "Alt+Q")
        snip_hk = config.get("HOTKEY_SNIP", "Alt+E")
        self.hotkey_show_edit.setKeySequence(QKeySequence(show_hk))
        self.hotkey_snip_edit.setKeySequence(QKeySequence(snip_hk))

        self.pet_enabled_check.setChecked(bool(config.get("PET_ENABLED", True)))
        pet_index = self.pet_combo.findData(config.get("PET_ID", "lihua"))
        self.pet_combo.setCurrentIndex(max(0, pet_index))
        self.pet_bubble_check.setChecked(bool(config.get("PET_BUBBLE_ENABLED", True)))
        self.pet_scale_slider.setValue(max(70, min(140, int(config.get("PET_SCALE", 100)))))
        
        # Apply theme immediately on load
        self.apply_theme_from_combo(self.theme_combo.currentIndex())

    def apply_theme_from_combo(self, index):
        theme_name = normalize_theme(self.theme_combo.itemData(index))
        palette = theme_palette(theme_name)
        bg_main = palette["settings_bg"]
        bg_sidebar = palette["settings_sidebar"]
        bg_card = palette["settings_card"]
        text_main = palette["text"]
        text_desc = palette["muted"]
        sidebar_text = palette["sidebar_text"]
        border_col = palette["border"]
        input_bg = palette["settings_input"]
        input_border = palette["settings_input_border"]
        list_hover = palette["settings_hover"]
        list_selected = palette["primary"]
        list_sel_text = "#FFFFFF"
        btn_bg = palette["settings_button"]
        btn_hover = palette["settings_button_hover"]
        btn_text = palette["settings_button_text"]
        primary_bg = palette["primary"]
        primary_hover = palette["primary_hover"]
        divider_col = palette["divider"]
        for combo in self.findChildren(ClearArrowComboBox):
            combo.set_arrow_color(text_desc)
        texture_path = theme_texture_path(theme_name)
        texture_rule = ""
        if texture_path:
            texture_rule = f"border-image: url('{texture_path.as_posix()}') 0 0 0 0 stretch stretch;"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_main};
                {texture_rule}
                color: {text_main};
                font-family: 'Segoe UI', 'Microsoft YaHei';
            }}
            
            QFrame#sidebarPanel {{
                background-color: {bg_sidebar};
                border: none;
                border-right: 1px solid {border_col};
            }}
            QLabel#sidebarBrand {{
                color: #FFFFFF;
                font-size: 16px;
                font-weight: 700;
            }}
            QLabel#sidebarCaption {{
                color: {sidebar_text};
                font-size: 11px;
            }}

            QListWidget#sidebar {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#sidebar::item {{
                color: {sidebar_text};
                padding: 8px 12px;
                margin: 3px 0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QListWidget#sidebar::item:hover {{
                background-color: {list_hover};
            }}
            QListWidget#sidebar::item:selected {{
                background-color: {list_selected};
                color: {list_sel_text};
                font-weight: 700;
            }}
            
            /* Right Area */
            QWidget#rightWidget {{
                background-color: {bg_main};
            }}
            QLabel#pageTitle {{
                color: {text_main};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#pageDescription {{
                color: {text_desc};
                font-size: 12px;
                margin-bottom: 5px;
            }}

            /* Card styling */
            QFrame.settings-card {{
                background-color: {bg_card};
                border: 1px solid {border_col};
                border-radius: 8px;
            }}
            QLabel.card-title {{
                color: {text_main};
                font-size: 15px;
                font-weight: 700;
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
            QLineEdit, QTextEdit, QComboBox, QKeySequenceEdit {{
                background-color: {input_bg};
                color: {text_main};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                selection-background-color: {primary_bg};
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QKeySequenceEdit:focus {{
                border: 1px solid {primary_bg};
            }}
            QComboBox::drop-down {{
                background-color: {btn_bg};
                border: none;
                border-left: 1px solid {input_border};
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                width: 38px;
            }}
            QCheckBox {{
                color: {text_main};
                font-size: 13px;
                spacing: 9px;
                min-height: 28px;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background-color: {input_border};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {primary_bg};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border-radius: 9px;
                background-color: {bg_card};
                border: 2px solid {primary_bg};
            }}
            QComboBox::drop-down:hover {{
                background-color: {btn_hover};
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_card};
                color: {text_main};
                border: 1px solid {input_border};
                border-radius: 6px;
                outline: none;
                padding: 5px;
                selection-background-color: {primary_bg};
                selection-color: white;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 32px;
                padding: 4px 9px;
            }}
            
            /* Button styling */
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
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
        theme_val = normalize_theme(self.theme_combo.currentData())
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
            "XIAOMI_TTS_MODEL": self.xiaomi_model_input.text().strip() or "mimo-v2.5-tts",
            "XIAOMI_TTS_VOICE": self.xiaomi_voice_combo.currentText(),
            "XIAOMI_TTS_STYLE": self.xiaomi_style_input.toPlainText().strip(),
            "AUDIO_PLAYER": "mpv" if self.player_combo.currentIndex() == 1 else "pygame",
            "HOTKEY_SHOW": self.hotkey_show_edit.keySequence().toString(),
            "HOTKEY_SNIP": self.hotkey_snip_edit.keySequence().toString(),
            "PET_ENABLED": self.pet_enabled_check.isChecked(),
            "PET_ID": self.pet_combo.currentData() or "lihua",
            "PET_BUBBLE_ENABLED": self.pet_bubble_check.isChecked(),
            "PET_SCALE": self.pet_scale_slider.value(),
        }
        merged_config = load_app_config()
        merged_config.update(new_config)
        save_app_config(merged_config)
        QMessageBox.information(self, "成功", "设置已保存，立即生效！")
        self.accept()
