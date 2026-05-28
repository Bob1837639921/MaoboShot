import os
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
                               QFrame, QGraphicsDropShadowEffect, QScrollArea)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor

class Ui_FloatingWindow:
    def setupUi(self, window):
        window.main_layout = QVBoxLayout()
        # 预留外边距给阴影效果
        window.main_layout.setContentsMargins(15, 15, 15, 15)
        
        window.container = QFrame()
        window.container.setObjectName("container")
        
        # 增加硬件级窗口阴影
        shadow = QGraphicsDropShadowEffect(window)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 160))
        window.container.setGraphicsEffect(shadow)
        
        window.content_layout = QVBoxLayout()
        window.content_layout.setContentsMargins(15, 15, 15, 15)
        window.content_layout.setSpacing(10)

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
        window.input_layout = QHBoxLayout()
        window.input_layout.setSpacing(8)
        window.input_edit = QTextEdit()
        window.input_edit.setPlaceholderText("手动输入 / 划词复制 / Alt+Z 截图...")
        window.input_edit.setMaximumHeight(80)
        window.input_edit.setMinimumHeight(80)
        
        # === 立即翻译按钮 ===
        window.translate_btn = QPushButton("翻译\n↵")
        window.translate_btn.setToolTip("快捷键: Enter (换行请用 Shift+Enter)")
        window.translate_btn.setFixedSize(60, 80)
        window.translate_btn.setCursor(Qt.PointingHandCursor)
        window.translate_btn.clicked.connect(window.on_translate_clicked)
        
        window.input_layout.addWidget(window.input_edit)
        window.input_layout.addWidget(window.translate_btn)

        # === 结果展示区域 ===
        # 1. 豆包 AI 结果区域
        window.ai_title_lbl = QLabel("✨ 豆包 AI")
        window.ai_result_lbl = QLabel()
        window.ai_result_lbl.setWordWrap(True)
        window.ai_result_lbl.setTextFormat(Qt.RichText)
        window.ai_result_lbl.setOpenExternalLinks(True)
        window.ai_result_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        
        window.ai_scroll = QScrollArea()
        window.ai_scroll.setWidget(window.ai_result_lbl)
        window.ai_scroll.setWidgetResizable(True)
        window.ai_scroll.setFrameShape(QFrame.Shape.NoFrame)
        window.ai_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.ai_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        window.ai_scroll.setAttribute(Qt.WA_TranslucentBackground)

        # 2. 谷歌翻译结果区域
        window.google_title_lbl = QLabel("🌐 谷歌翻译")
        window.google_result_lbl = QLabel()
        window.google_result_lbl.setWordWrap(True)
        window.google_result_lbl.setTextFormat(Qt.RichText)
        window.google_result_lbl.setOpenExternalLinks(True)
        window.google_result_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        
        window.google_scroll = QScrollArea()
        window.google_scroll.setWidget(window.google_result_lbl)
        window.google_scroll.setWidgetResizable(True)
        window.google_scroll.setFrameShape(QFrame.Shape.NoFrame)
        window.google_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        window.google_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        window.google_scroll.setAttribute(Qt.WA_TranslucentBackground)

        # === 朗读按钮 ===
        window.play_btn = QPushButton("🔊 朗读原文")
        window.play_btn.setCursor(Qt.PointingHandCursor)
        window.play_btn.clicked.connect(window.play_audio)

        window.content_layout.addLayout(window.header_layout)
        window.content_layout.addLayout(window.input_layout)
        window.content_layout.addWidget(window.ai_title_lbl)
        window.content_layout.addWidget(window.ai_scroll)
        window.content_layout.addWidget(window.google_title_lbl)
        window.content_layout.addWidget(window.google_scroll)
        window.content_layout.addWidget(window.play_btn)
        
        window.container.setLayout(window.content_layout)
        window.main_layout.addWidget(window.container)
        window.setLayout(window.main_layout)

        window.hide_results()
        window.setFixedWidth(500)
        window.adjustSize()
        
        # === 弹窗淡入动画 ===
        window.fade_anim = QPropertyAnimation(window, b"windowOpacity")
        window.fade_anim.setDuration(150)
        window.fade_anim.setStartValue(0.0)
        window.fade_anim.setEndValue(1.0)
        window.fade_anim.setEasingCurve(QEasingCurve.OutQuad)

def apply_window_theme(window, theme_name):
    if theme_name == "light":
        bg_color = "rgba(245, 245, 245, 245)"
        border_color = "rgba(200, 200, 200, 150)"
        title_color = "#666666"
        close_btn_color = "#888888"
        input_bg = "rgba(255, 255, 255, 200)"
        input_text = "#333333"
        input_border = "rgba(200, 200, 200, 180)"
        result_text = "#333333"
        play_btn_bg = "#1a73e8"
        play_btn_hover = "#2b84f3"
        
        window.html_vars = {
            "card_bg": "rgba(0,0,0,0.05)",
            "phonetic_bg": "rgba(0,0,0,0.08)",
            "phonetic_text": "#666666",
            "divider": "rgba(0,0,0,0.08)",
            "ai_title": "#0067C0",
            "google_title": "#d97b00",
            "placeholder": "#888888"
        }
    else:
        bg_color = "rgba(30, 30, 30, 245)"
        border_color = "rgba(80, 80, 80, 150)"
        title_color = "#999999"
        close_btn_color = "#888888"
        input_bg = "rgba(15, 15, 15, 150)"
        input_text = "#ffffff"
        input_border = "rgba(80, 80, 80, 150)"
        result_text = "#e0e0e0"
        play_btn_bg = "#1a73e8"
        play_btn_hover = "#2b84f3"
        
        window.html_vars = {
            "card_bg": "rgba(0,0,0,0.15)",
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
            border-radius: 12px;
        }}
    """)
    
    window.title_label.setStyleSheet(f"color: {title_color}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px; font-weight: bold;")
    
    window.close_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {close_btn_color};
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 12px;
        }}
        QPushButton:hover {{ background-color: #ff4d4f; color: white; }}
    """)
    
    window.input_edit.setStyleSheet(f"""
        QTextEdit {{ 
            background-color: {input_bg}; 
            color: {input_text}; 
            border: 1px solid {input_border}; 
            border-radius: 8px; 
            font-family: 'Segoe UI', 'Microsoft YaHei'; 
            font-size: 14px; 
            padding: 8px; 
        }}
        QTextEdit:focus {{
            border: 1px solid #1a73e8;
        }}
    """)
    
    window.ai_title_lbl.setStyleSheet(f"QLabel {{ color: {window.html_vars.get('ai_title')}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 13px; font-weight: bold; }}")
    window.google_title_lbl.setStyleSheet(f"QLabel {{ color: {window.html_vars.get('google_title')}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 13px; font-weight: bold; }}")
    
    window.ai_result_lbl.setStyleSheet(f"QLabel {{ color: {result_text}; background: transparent; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; padding: 10px; }}")
    window.google_result_lbl.setStyleSheet(f"QLabel {{ color: {result_text}; background: transparent; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; padding: 10px; }}")
    
    card_bg = window.html_vars.get("card_bg")
    scroll_style = f"""
        QScrollArea {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: 8px;
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
        QScrollBar::handle:vertical:hover {{
            background: rgba(120, 120, 120, 180);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
    """
    window.ai_scroll.setStyleSheet(scroll_style)
    window.google_scroll.setStyleSheet(scroll_style)
    
    window.play_btn.setStyleSheet(f"""
        QPushButton {{ 
            background-color: {play_btn_bg}; 
            color: white; 
            border: none; 
            border-radius: 8px; 
            padding: 8px 16px; 
            font-family: 'Segoe UI', 'Microsoft YaHei'; 
            font-size: 13px;
            font-weight: bold; 
        }} 
        QPushButton:hover {{ background-color: {play_btn_hover}; }}
        QPushButton:pressed {{ background-color: #1257b5; }}
        QPushButton:disabled {{ background-color: #555555; color: #aaaaaa; }}
    """)

    window.translate_btn.setStyleSheet(f"""
        QPushButton {{ 
            background-color: {play_btn_bg}; 
            color: white; 
            border: none; 
            border-radius: 8px; 
            font-family: 'Segoe UI', 'Microsoft YaHei'; 
            font-size: 14px;
            font-weight: bold; 
        }} 
        QPushButton:hover {{ background-color: {play_btn_hover}; }}
        QPushButton:pressed {{ background-color: #1257b5; }}
    """)
