import os
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
                               QFrame, QGraphicsDropShadowEffect, QScrollArea, QWidget)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor

class Ui_FloatingWindow:
    def setupUi(self, window):
        window.main_layout = QVBoxLayout()
        # 预留外边距给阴影效果
        window.main_layout.setContentsMargins(20, 20, 20, 20)
        
        window.container = QFrame()
        window.container.setObjectName("container")
        
        # 增加硬件级窗口阴影
        shadow = QGraphicsDropShadowEffect(window)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 120))
        window.container.setGraphicsEffect(shadow)
        
        window.content_layout = QVBoxLayout()
        window.content_layout.setContentsMargins(15, 15, 15, 15)
        window.content_layout.setSpacing(12)

        # === 顶部拖拽把手与控制栏 ===
        window.header_layout = QHBoxLayout()
        window.header_layout.setContentsMargins(0, 0, 0, 0)
        
        window.title_label = QLabel("✨ ManboShot")
        
        window.close_btn = QPushButton("×")
        window.close_btn.setFixedSize(24, 24)
        window.close_btn.setCursor(Qt.PointingHandCursor)
        window.close_btn.clicked.connect(window.hide)
        
        window.header_layout.addWidget(window.title_label)
        window.header_layout.addStretch()
        window.header_layout.addWidget(window.close_btn)

        # === 输入框 ===
        window.input_edit = QTextEdit()
        window.input_edit.setPlaceholderText("在此输入 / 双击 Ctrl+C 划词 / Alt+E 截图 / Alt+Q 唤起...")
        window.input_edit.setMaximumHeight(100)
        window.input_edit.setMinimumHeight(60)
        
        # === 快捷工具栏 (紧贴输入框下方) ===
        window.toolbar_layout = QHBoxLayout()
        window.toolbar_layout.setContentsMargins(2, 0, 2, 0)
        
        window.settings_btn = QPushButton("⚙️")
        window.settings_btn.setFixedSize(28, 28)
        window.settings_btn.setToolTip("设置中心")
        window.settings_btn.setCursor(Qt.PointingHandCursor)
        window.settings_btn.clicked.connect(window.show_settings)

        window.translate_btn = QPushButton("✈ 翻译 (Enter)")
        window.translate_btn.setFixedHeight(30)
        window.translate_btn.setCursor(Qt.PointingHandCursor)
        window.translate_btn.clicked.connect(window.on_translate_clicked)
        
        window.toolbar_layout.addWidget(window.settings_btn)
        window.toolbar_layout.addStretch()
        window.toolbar_layout.addWidget(window.translate_btn)

        # === 结果展示区域 ===
        from PySide6.QtWidgets import QAbstractScrollArea
        window.main_scroll = QScrollArea()
        window.main_scroll.setWidgetResizable(True)
        window.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        window.main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        window.main_scroll.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        window.main_scroll.setAttribute(Qt.WA_TranslucentBackground)
        
        window.scroll_content = QFrame()
        window.scroll_content.setObjectName("scroll_content")
        window.scroll_layout = QVBoxLayout(window.scroll_content)
        window.scroll_layout.setContentsMargins(0, 5, 0, 5)
        window.scroll_layout.setSpacing(10)

        # 1. 豆包 AI 结果区域
        window.ai_title_lbl = QLabel("✨ 豆包 AI")
        window.ai_result_lbl = QLabel()
        window.ai_result_lbl.setWordWrap(True)
        window.ai_result_lbl.setTextFormat(Qt.RichText)
        window.ai_result_lbl.setOpenExternalLinks(True)
        window.ai_result_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        
        # 2. 谷歌翻译结果区域
        window.google_title_lbl = QLabel("🌐 谷歌翻译")
        window.google_result_lbl = QLabel()
        window.google_result_lbl.setWordWrap(True)
        window.google_result_lbl.setTextFormat(Qt.RichText)
        window.google_result_lbl.setOpenExternalLinks(True)
        window.google_result_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        
        window.scroll_layout.addWidget(window.ai_title_lbl)
        window.scroll_layout.addWidget(window.ai_result_lbl)
        window.scroll_layout.addWidget(window.google_title_lbl)
        window.scroll_layout.addWidget(window.google_result_lbl)
        window.scroll_layout.addStretch()
        
        window.main_scroll.setWidget(window.scroll_content)

        # === 底部朗读按钮 (Status Bar) ===
        window.play_btn = QPushButton("🔊 朗读原文")
        window.play_btn.setFixedHeight(36)
        window.play_btn.setCursor(Qt.PointingHandCursor)
        window.play_btn.clicked.connect(window.play_audio)

        window.content_layout.addLayout(window.header_layout)
        window.content_layout.addWidget(window.input_edit)
        window.content_layout.addLayout(window.toolbar_layout)
        window.content_layout.addWidget(window.main_scroll)
        window.content_layout.addWidget(window.play_btn)
        
        window.container.setLayout(window.content_layout)
        window.main_layout.addWidget(window.container)
        window.setLayout(window.main_layout)

        window.hide_results()
        window.setFixedWidth(340)
        window.adjustSize()
        
        # === 弹窗淡入动画 ===
        window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
        window.fade_anim.setDuration(150)
        window.fade_anim.setStartValue(0.0)
        window.fade_anim.setEndValue(1.0)
        window.fade_anim.setEasingCurve(QEasingCurve.OutQuad)

def apply_window_theme(window, theme_name):
    if theme_name == "light":
        bg_color = "rgba(250, 250, 250, 248)"
        border_color = "rgba(200, 200, 200, 150)"
        title_color = "#555555"
        close_btn_color = "#888888"
        input_bg = "rgba(255, 255, 255, 255)"
        input_text = "#333333"
        input_border = "rgba(200, 200, 200, 180)"
        result_text = "#2c3e50"
        play_btn_bg = "#1a73e8"
        play_btn_hover = "#2b84f3"
        
        window.html_vars = {
            "card_bg": "rgba(0,0,0,0.03)",
            "bubble_bg": "rgba(255,255,255,0.9)",
            "phonetic_bg": "rgba(0,0,0,0.06)",
            "phonetic_text": "#666666",
            "divider": "rgba(0,0,0,0.08)",
            "ai_title": "#0067C0",
            "google_title": "#d97b00",
            "placeholder": "#888888"
        }
    else:
        bg_color = "rgba(28, 28, 30, 248)"
        border_color = "rgba(60, 60, 60, 180)"
        title_color = "#aaaaaa"
        close_btn_color = "#888888"
        input_bg = "rgba(40, 40, 42, 255)"
        input_text = "#f0f0f0"
        input_border = "rgba(70, 70, 75, 180)"
        result_text = "#e0e0e0"
        play_btn_bg = "#0A84FF"
        play_btn_hover = "#409CFF"
        
        window.html_vars = {
            "card_bg": "rgba(0,0,0,0.2)",
            "bubble_bg": "rgba(50,50,55,0.6)",
            "phonetic_bg": "rgba(255,255,255,0.1)",
            "phonetic_text": "#aaaaaa",
            "divider": "rgba(255,255,255,0.1)",
            "ai_title": "#5bc0de",
            "google_title": "#f0ad4e",
            "placeholder": "#888888"
        }

    window.container.setStyleSheet(f"""
        QFrame#container {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 14px;
        }}
    """)
    
    window.title_label.setStyleSheet(f"color: {title_color}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px; font-weight: bold;")
    
    window.close_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {close_btn_color};
            border: none;
            font-size: 18px;
            font-weight: bold;
            padding-bottom: 2px;
        }}
        QPushButton:hover {{
            color: #ff4d4d;
        }}
    """)
    
    window.input_edit.setStyleSheet(f"""
        QTextEdit {{ 
            background-color: {input_bg}; 
            color: {input_text}; 
            border: 1px solid {input_border}; 
            border-radius: 10px; 
            font-family: 'Segoe UI', 'Microsoft YaHei'; 
            font-size: 15px; 
            padding: 12px; 
        }}
        QTextEdit:focus {{
            border: 1px solid {play_btn_bg};
        }}
    """)
    
    window.settings_btn.setStyleSheet(f"""
        QPushButton {{ background: transparent; border: none; border-radius: 14px; font-size: 16px; }}
        QPushButton:hover {{ background: {window.html_vars.get('card_bg')}; }}
    """)
    
    window.translate_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {play_btn_bg};
            color: white;
            border: none;
            border-radius: 15px;
            padding: 0 16px;
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 13px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {play_btn_hover};
        }}
    """)

    window.ai_title_lbl.setStyleSheet(f"QLabel {{ color: {window.html_vars.get('ai_title')}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 13px; font-weight: bold; margin-left: 4px; }}")
    window.google_title_lbl.setStyleSheet(f"QLabel {{ color: {window.html_vars.get('google_title')}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 13px; font-weight: bold; margin-left: 4px; }}")
    
    bubble_bg = window.html_vars.get('bubble_bg')
    window.ai_result_lbl.setStyleSheet(f"QLabel {{ color: {result_text}; background: {bubble_bg}; border-radius: 10px; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; padding: 14px; margin-bottom: 8px; line-height: 1.6; border: 1px solid {border_color}; }}")
    window.google_result_lbl.setStyleSheet(f"QLabel {{ color: {result_text}; background: {bubble_bg}; border-radius: 10px; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; padding: 14px; line-height: 1.6; border: 1px solid {border_color}; }}")
    
    scroll_style = f"""
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        QFrame#scroll_content {{
            background-color: transparent;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(120, 120, 120, 100);
            min-height: 20px;
            border-radius: 3px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(120, 120, 120, 180);
        }}
    """
    window.main_scroll.setStyleSheet(scroll_style)
    
    window.play_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {window.html_vars.get('card_bg')};
            color: {result_text};
            border: 1px solid {border_color};
            border-radius: 10px;
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {bubble_bg};
        }}
    """)
