from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
)
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ui.theme import normalize_theme, theme_palette, theme_texture_path


class TexturedContainer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._texture = QPixmap()
        self._scaled_texture = QPixmap()
        self._texture_opacity = 0.0
        self._theme_name = "dark"
        self._accent = QColor("#3B82F6")
        self._scan_phase = 0
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(80)
        self._scan_timer.timeout.connect(self._advance_scan)

    def set_theme_visual(self, theme_name, texture_path, opacity, accent):
        self._theme_name = normalize_theme(theme_name)
        self._texture_opacity = float(opacity)
        self._accent = QColor(accent)
        self._texture = QPixmap(str(texture_path)) if texture_path else QPixmap()
        self._refresh_scaled_texture()

        if self._texture.isNull():
            self._scan_timer.stop()
            self._scan_phase = 0
        elif self.isVisible() and not self._scan_timer.isActive():
            self._scan_timer.start()
        self.update()

    def _refresh_scaled_texture(self):
        if self._texture.isNull() or self.width() <= 0 or self.height() <= 0:
            self._scaled_texture = QPixmap()
            return
        self._scaled_texture = self._texture.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

    def _advance_scan(self):
        self._scan_phase = (self._scan_phase + 3) % max(1, self.height() + 80)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_scaled_texture()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._texture.isNull() and not self._scan_timer.isActive():
            self._scan_timer.start()

    def hideEvent(self, event):
        self._scan_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._scaled_texture.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(self.rect().adjusted(1, 1, -1, -1)), 7, 7)
        painter.setClipPath(clip_path)

        x = (self.width() - self._scaled_texture.width()) // 2
        y = (self.height() - self._scaled_texture.height()) // 2
        painter.setOpacity(self._texture_opacity)
        painter.drawPixmap(x, y, self._scaled_texture)

        painter.setOpacity(1.0)
        scan_y = self._scan_phase - 40
        scan_color = QColor(self._accent)
        scan_color.setAlpha(34 if self._theme_name != "blueprint" else 24)
        painter.setPen(QPen(scan_color, 1))
        painter.drawLine(14, scan_y, max(14, self.width() - 14), scan_y)

        glow_color = QColor(self._accent)
        glow_color.setAlpha(12)
        painter.setPen(QPen(glow_color, 7))
        painter.drawLine(20, scan_y, max(20, self.width() - 20), scan_y)


class Ui_FloatingWindow:
    def setupUi(self, window):
        window.main_layout = QVBoxLayout()
        window.main_layout.setContentsMargins(12, 12, 12, 12)

        window.container = TexturedContainer()
        window.container.setObjectName("container")

        shadow = QGraphicsDropShadowEffect(window)
        shadow.setBlurRadius(34)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 85))
        window.container.setGraphicsEffect(shadow)

        window.content_layout = QVBoxLayout()
        window.content_layout.setContentsMargins(16, 14, 16, 16)
        window.content_layout.setSpacing(10)

        window.header_layout = QHBoxLayout()
        window.header_layout.setContentsMargins(0, 0, 0, 2)
        window.header_layout.setSpacing(8)

        window.brand_mark = QFrame()
        window.brand_mark.setObjectName("brandMark")
        window.brand_mark.setFixedSize(4, 22)

        window.title_label = QLabel("ManboShot")
        window.status_label = QLabel("就绪")
        window.status_label.setObjectName("statusLabel")

        window.settings_btn = QPushButton("⚙")
        window.settings_btn.setObjectName("headerToolButton")
        window.settings_btn.setFixedSize(28, 28)
        window.settings_btn.setToolTip("设置")
        window.settings_btn.setCursor(Qt.PointingHandCursor)
        window.settings_btn.clicked.connect(window.show_settings)

        window.close_btn = QPushButton("×")
        window.close_btn.setObjectName("closeButton")
        window.close_btn.setFixedSize(28, 28)
        window.close_btn.setToolTip("隐藏窗口")
        window.close_btn.setCursor(Qt.PointingHandCursor)
        window.close_btn.clicked.connect(window.hide)

        window.header_layout.addWidget(window.brand_mark)
        window.header_layout.addWidget(window.title_label)
        window.header_layout.addStretch()
        window.header_layout.addWidget(window.status_label)
        window.header_layout.addWidget(window.settings_btn)
        window.header_layout.addWidget(window.close_btn)

        window.input_edit = QTextEdit()
        window.input_edit.setObjectName("translationInput")
        window.input_edit.setPlaceholderText("输入或粘贴需要翻译的内容")
        window.input_edit.setAcceptRichText(False)
        window.input_edit.setMinimumHeight(72)
        window.input_edit.setMaximumHeight(120)

        window.toolbar_layout = QHBoxLayout()
        window.toolbar_layout.setContentsMargins(0, 0, 0, 2)
        window.toolbar_layout.setSpacing(8)

        window.mode_label = QLabel("自动识别语言")
        window.mode_label.setObjectName("modeLabel")

        window.translate_btn = QPushButton("翻译")
        window.translate_btn.setObjectName("translateButton")
        window.translate_btn.setFixedSize(96, 34)
        window.translate_btn.setCursor(Qt.PointingHandCursor)
        window.translate_btn.clicked.connect(window.on_translate_clicked)

        window.toolbar_layout.addWidget(window.mode_label)
        window.toolbar_layout.addStretch()
        window.toolbar_layout.addWidget(window.translate_btn)

        window.ocr_panel = QFrame()
        window.ocr_panel.setObjectName("ocrPanel")
        ocr_layout = QVBoxLayout(window.ocr_panel)
        ocr_layout.setContentsMargins(16, 15, 16, 15)
        ocr_layout.setSpacing(7)

        ocr_header = QHBoxLayout()
        ocr_header.setContentsMargins(0, 0, 0, 0)
        ocr_header.setSpacing(8)

        window.ocr_status_dot = QLabel("●")
        window.ocr_status_dot.setObjectName("ocrStatusDot")
        window.ocr_status_dot.setFixedWidth(10)
        window.ocr_status_title = QLabel("正在识别截图")
        window.ocr_status_title.setObjectName("ocrStatusTitle")

        window.ocr_retry_btn = QPushButton("重新截图")
        window.ocr_retry_btn.setObjectName("ocrRetryButton")
        window.ocr_retry_btn.setFixedSize(72, 28)
        window.ocr_retry_btn.setCursor(Qt.PointingHandCursor)
        window.ocr_retry_btn.clicked.connect(window.start_snipping)

        ocr_header.addWidget(window.ocr_status_dot)
        ocr_header.addWidget(window.ocr_status_title)
        ocr_header.addStretch()
        ocr_header.addWidget(window.ocr_retry_btn)

        window.ocr_status_desc = QLabel("正在提取文字并恢复排版")
        window.ocr_status_desc.setObjectName("ocrStatusDescription")
        window.ocr_progress = QProgressBar()
        window.ocr_progress.setObjectName("ocrProgress")
        window.ocr_progress.setRange(0, 0)
        window.ocr_progress.setTextVisible(False)
        window.ocr_progress.setFixedHeight(4)

        ocr_layout.addLayout(ocr_header)
        ocr_layout.addWidget(window.ocr_status_desc)
        ocr_layout.addSpacing(2)
        ocr_layout.addWidget(window.ocr_progress)
        window.ocr_panel.hide()

        window.main_scroll = QScrollArea()
        window.main_scroll.setWidgetResizable(True)
        window.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        window.main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        window.main_scroll.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        window.main_scroll.setAttribute(Qt.WA_TranslucentBackground)

        window.scroll_content = QFrame()
        window.scroll_content.setObjectName("scrollContent")
        window.scroll_layout = QVBoxLayout(window.scroll_content)
        window.scroll_layout.setContentsMargins(0, 4, 0, 4)
        window.scroll_layout.setSpacing(10)

        def create_result_card(object_name, title, copy_callback):
            card = QFrame()
            card.setObjectName(object_name)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(13, 11, 13, 13)
            card_layout.setSpacing(8)

            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(7)

            dot = QLabel("●")
            dot.setObjectName(f"{object_name}Dot")
            dot.setFixedWidth(10)

            title_label = QLabel(title)
            title_label.setObjectName(f"{object_name}Title")

            copy_button = QPushButton("复制")
            copy_button.setObjectName("copyButton")
            copy_button.setFixedSize(48, 26)
            copy_button.setToolTip(f"复制{title}结果")
            copy_button.setCursor(Qt.PointingHandCursor)
            copy_button.setEnabled(False)
            copy_button.clicked.connect(copy_callback)

            header.addWidget(dot)
            header.addWidget(title_label)
            header.addStretch()
            header.addWidget(copy_button)

            result_label = QLabel()
            result_label.setObjectName("resultText")
            result_label.setWordWrap(True)
            result_label.setTextFormat(Qt.RichText)
            result_label.setOpenExternalLinks(True)
            result_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
            )

            card_layout.addLayout(header)
            card_layout.addWidget(result_label)
            return card, title_label, result_label, copy_button, header

        (
            window.ai_card,
            window.ai_title_lbl,
            window.ai_result_lbl,
            window.ai_copy_btn,
            ai_header,
        ) = create_result_card("aiCard", "AI 翻译", lambda: window.copy_result("ai"))

        window.ai_retry_btn = QPushButton("重试")
        window.ai_retry_btn.setObjectName("retryButton")
        window.ai_retry_btn.setFixedSize(48, 26)
        window.ai_retry_btn.setToolTip("重新请求 AI 翻译")
        window.ai_retry_btn.setCursor(Qt.PointingHandCursor)
        window.ai_retry_btn.clicked.connect(window.retry_ai_translation)
        window.ai_retry_btn.hide()
        ai_header.insertWidget(ai_header.count() - 1, window.ai_retry_btn)

        (
            window.google_card,
            window.google_title_lbl,
            window.google_result_lbl,
            window.google_copy_btn,
            _google_header,
        ) = create_result_card(
            "googleCard", "Google 翻译", lambda: window.copy_result("google")
        )

        window.scroll_layout.addWidget(window.ai_card)
        window.scroll_layout.addWidget(window.google_card)
        window.main_scroll.setWidget(window.scroll_content)

        window.play_btn = QPushButton("朗读原文")
        window.play_btn.setObjectName("playButton")
        window.play_btn.setFixedHeight(34)
        window.play_btn.setCursor(Qt.PointingHandCursor)
        window.play_btn.clicked.connect(window.play_audio)

        window.content_layout.addLayout(window.header_layout)
        window.content_layout.addWidget(window.input_edit)
        window.content_layout.addLayout(window.toolbar_layout)
        window.content_layout.addWidget(window.ocr_panel)
        window.content_layout.addWidget(window.main_scroll)
        window.content_layout.addWidget(window.play_btn)

        window.container.setLayout(window.content_layout)
        window.main_layout.addWidget(window.container)
        window.setLayout(window.main_layout)

        window.hide_results()
        window.setFixedWidth(380)
        window.adjustSize()

        window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
        window.fade_anim.setDuration(140)
        window.fade_anim.setStartValue(0.0)
        window.fade_anim.setEndValue(1.0)
        window.fade_anim.setEasingCurve(QEasingCurve.OutCubic)


def apply_window_theme(window, theme_name):
    theme_name = normalize_theme(theme_name)
    palette = theme_palette(theme_name)
    window_bg = palette["window_bg"]
    surface = palette["surface"]
    surface_subtle = palette["surface_subtle"]
    border = palette["border"]
    text = palette["text"]
    muted = palette["muted"]
    primary = palette["primary"]
    primary_hover = palette["primary_hover"]
    primary_pressed = palette["primary_pressed"]
    ai_accent = palette["ai_accent"]
    ai_surface = palette["ai_surface"]
    google_accent = palette["google_accent"]
    google_surface = palette["google_surface"]
    danger = palette["danger"]
    shadow_button = palette["shadow_button"]

    window.container.set_theme_visual(
        theme_name,
        theme_texture_path(theme_name),
        palette["texture_opacity"],
        primary,
    )

    window.html_vars = {
        "card_bg": surface_subtle,
        "bubble_bg": surface,
        "phonetic_bg": shadow_button,
        "phonetic_text": muted,
        "divider": border,
        "ai_title": ai_accent,
        "google_title": google_accent,
        "placeholder": muted,
        "primary": primary,
        "danger": danger,
    }

    window.container.setStyleSheet(
        f"""
        QFrame#container {{
            background-color: {window_bg};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        """
    )

    window.brand_mark.setStyleSheet(
        f"background-color: {primary}; border: none; border-radius: 2px;"
    )
    window.title_label.setStyleSheet(
        f"color: {text}; font-family: 'Segoe UI', 'Microsoft YaHei'; "
        "font-size: 14px; font-weight: 700;"
    )
    window.status_label.setStyleSheet(
        f"color: {muted}; background: {surface_subtle}; border: 1px solid {border}; "
        "border-radius: 6px; padding: 3px 7px; font-size: 11px;"
    )

    window.settings_btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent; color: {muted}; border: none;
            border-radius: 6px; font-size: 15px;
        }}
        QPushButton:hover {{ background: {surface_subtle}; color: {text}; }}
        """
    )
    window.close_btn.setStyleSheet(
        f"""
        QPushButton {{
            background: transparent; color: {muted}; border: none;
            border-radius: 6px; font-size: 19px; padding-bottom: 2px;
        }}
        QPushButton:hover {{ background: {surface_subtle}; color: {danger}; }}
        """
    )

    window.input_edit.setStyleSheet(
        f"""
        QTextEdit#translationInput {{
            background-color: {surface}; color: {text}; border: 1px solid {border};
            border-radius: 8px; font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 15px; padding: 11px; selection-background-color: {primary};
        }}
        QTextEdit#translationInput:focus {{ border: 2px solid {primary}; padding: 10px; }}
        """
    )
    window.mode_label.setStyleSheet(
        f"color: {muted}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 11px;"
    )
    window.translate_btn.setStyleSheet(
        f"""
        QPushButton#translateButton {{
            background-color: {primary}; color: white; border: none;
            border-radius: 7px; font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 13px; font-weight: 700;
        }}
        QPushButton#translateButton:hover {{ background-color: {primary_hover}; }}
        QPushButton#translateButton:pressed {{ background-color: {primary_pressed}; }}
        """
    )

    window.ocr_panel.setStyleSheet(
        f"QFrame#ocrPanel {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}"
    )
    window.ocr_status_dot.setStyleSheet(f"color: {primary}; font-size: 9px;")
    window.ocr_status_title.setStyleSheet(
        f"color: {text}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; font-weight: 700;"
    )
    window.ocr_status_desc.setStyleSheet(
        f"color: {muted}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px;"
    )
    window.ocr_progress.setStyleSheet(
        f"""
        QProgressBar#ocrProgress {{ background: {surface_subtle}; border: none; border-radius: 2px; }}
        QProgressBar#ocrProgress::chunk {{ background: {primary}; border-radius: 2px; width: 36px; }}
        """
    )
    window.ocr_retry_btn.setStyleSheet(
        f"""
        QPushButton#ocrRetryButton {{
            background: {primary}; color: white; border: none; border-radius: 6px;
            font-size: 11px; font-weight: 700;
        }}
        QPushButton#ocrRetryButton:hover {{ background: {primary_hover}; }}
        """
    )

    window.ai_card.setStyleSheet(
        f"QFrame#aiCard {{ background: {ai_surface}; border: 1px solid {border}; border-radius: 8px; }}"
    )
    window.google_card.setStyleSheet(
        f"QFrame#googleCard {{ background: {google_surface}; border: 1px solid {border}; border-radius: 8px; }}"
    )
    window.ai_card.findChild(QLabel, "aiCardDot").setStyleSheet(
        f"color: {ai_accent}; font-size: 9px;"
    )
    window.google_card.findChild(QLabel, "googleCardDot").setStyleSheet(
        f"color: {google_accent}; font-size: 9px;"
    )
    window.ai_title_lbl.setStyleSheet(
        f"color: {ai_accent}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px; font-weight: 700;"
    )
    window.google_title_lbl.setStyleSheet(
        f"color: {google_accent}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px; font-weight: 700;"
    )
    result_style = (
        f"QLabel#resultText {{ color: {text}; background: transparent; border: none; "
        "font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; padding: 1px; }}"
    )
    window.ai_result_lbl.setStyleSheet(result_style)
    window.google_result_lbl.setStyleSheet(result_style)

    copy_style = f"""
        QPushButton#copyButton {{
            background: transparent; color: {muted}; border: 1px solid {border};
            border-radius: 5px; font-size: 11px; font-weight: 600;
        }}
        QPushButton#copyButton:hover {{ background: {surface}; color: {text}; }}
        QPushButton#copyButton:disabled {{ color: {border}; background: transparent; }}
    """
    window.ai_copy_btn.setStyleSheet(copy_style)
    window.google_copy_btn.setStyleSheet(copy_style)
    window.ai_retry_btn.setStyleSheet(
        f"""
        QPushButton#retryButton {{
            background: {primary}; color: white; border: none;
            border-radius: 5px; font-size: 11px; font-weight: 700;
        }}
        QPushButton#retryButton:hover {{ background: {primary_hover}; }}
        QPushButton#retryButton:pressed {{ background: {primary_pressed}; }}
        """
    )

    window.main_scroll.setStyleSheet(
        f"""
        QScrollArea {{ background: transparent; border: none; }}
        QFrame#scrollContent {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ border: none; background: transparent; width: 6px; }}
        QScrollBar::handle:vertical {{ background: {border}; min-height: 24px; border-radius: 3px; }}
        QScrollBar::handle:vertical:hover {{ background: {muted}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
        """
    )

    window.play_btn.setStyleSheet(
        f"""
        QPushButton#playButton {{
            background: {surface_subtle}; color: {text}; border: 1px solid {border};
            border-radius: 7px; font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 12px; font-weight: 600;
        }}
        QPushButton#playButton:hover {{ background: {surface}; border-color: {muted}; }}
        """
    )
