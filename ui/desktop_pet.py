import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import load_app_config, logger, save_app_config
from core.pet_pack import get_pet_pack
from core.pet_state import resolve_translation_state
from ui.theme import theme_palette


PET_STATES = {
    "idle",
    "ocr",
    "translating",
    "success",
    "partial_error",
    "error",
    "speaking",
}

STATE_ACTIONS = {
    "ocr": "waiting",
    "translating": "running",
    "success": "review",
    "partial_error": "failed",
    "error": "failed",
}


@dataclass
class SpriteArt:
    base: QPixmap = field(default_factory=QPixmap)
    back_layers: dict = field(default_factory=dict)
    front_layers: dict = field(default_factory=dict)
    pivots: dict = field(default_factory=dict)
    blink: QPixmap = field(default_factory=QPixmap)

    @property
    def width(self):
        return self.base.width()

    @property
    def height(self):
        return self.base.height()

    def isNull(self):
        return self.base.isNull()


def _pil_to_pixmap(image: Image.Image) -> QPixmap:
    rgba = np.ascontiguousarray(np.array(image.convert("RGBA")))
    qimage = QImage(
        rgba.data,
        rgba.shape[1],
        rgba.shape[0],
        rgba.strides[0],
        QImage.Format_RGBA8888,
    ).copy()
    return QPixmap.fromImage(qimage)


def _normalized_point(point, width, height):
    return (round(float(point[0]) * width), round(float(point[1]) * height))


def _build_blink_overlay(image: Image.Image, rig: dict) -> QPixmap:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    eyelid_fill = rig.get("eyelid_fill", "#5b4d38")
    eyelid_line = rig.get("eyelid_color", "#241d19")
    for eye in rig.get("eyes", []):
        left, top = _normalized_point(eye[:2], width, height)
        right, bottom = _normalized_point(eye[2:], width, height)
        eye_height = max(1, bottom - top)
        inset_x = max(2, (right - left) // 12)
        inset_y = max(2, eye_height // 10)
        draw.rounded_rectangle(
            (left + inset_x, top + inset_y, right - inset_x, bottom - inset_y),
            radius=max(2, eye_height // 3),
            fill=eyelid_fill,
        )
        line_y = top + eye_height // 2
        line_width = max(4, eye_height // 11)
        draw.line(
            (left + inset_x * 2, line_y, right - inset_x * 2, line_y),
            fill=eyelid_line,
            width=line_width,
        )
    return _pil_to_pixmap(overlay)


def _extract_sprite(path: Path, processing: dict, rig: dict = None) -> SpriteArt:
    try:
        source = Image.open(path).convert("RGBA")
    except (OSError, ValueError):
        return SpriteArt()

    image = np.array(source)
    alpha = image[:, :, 3]
    if processing.get("background") == "light-grid" and np.all(alpha == 255):
        rgb = image[:, :, :3].astype(np.int16)
        value = rgb.max(axis=2)
        color_range = rgb.max(axis=2) - rgb.min(axis=2)
        background = (value > 160) & (color_range < 46)
        foreground_mask = Image.fromarray((~background).astype(np.uint8) * 255)

        width, height = foreground_mask.size
        border_points = []
        border_points.extend((x, 0) for x in range(width))
        border_points.extend((x, height - 1) for x in range(width))
        border_points.extend((0, y) for y in range(height))
        border_points.extend((width - 1, y) for y in range(height))
        for point in border_points:
            if foreground_mask.getpixel(point) == 255:
                ImageDraw.floodfill(foreground_mask, point, 128, thresh=0)

        mask = np.array(foreground_mask)
        image[:, :, 3] = np.where(mask == 255, 255, 0).astype(np.uint8)

        # Remove pale grid remnants only along the silhouette boundary. This keeps
        # the tabby markings intact while preventing bright seams on moving limbs.
        opaque = image[:, :, 3] > 0
        light_neutral = (value > 145) & (color_range < 92)
        for _ in range(2):
            padded = np.pad(opaque, 1, constant_values=False)
            surrounded = np.ones_like(opaque)
            for y_offset in range(3):
                for x_offset in range(3):
                    surrounded &= padded[
                        y_offset : y_offset + opaque.shape[0],
                        x_offset : x_offset + opaque.shape[1],
                    ]
            remove = opaque & ~surrounded & light_neutral
            opaque[remove] = False
        image[:, :, 3] = np.where(opaque, 255, 0).astype(np.uint8)

    alpha_image = Image.fromarray(image[:, :, 3])
    bounds = alpha_image.getbbox()
    if bounds is None:
        return SpriteArt()

    padding = int(processing.get("padding", 0))
    left = max(0, bounds[0] - padding)
    top = max(0, bounds[1] - padding)
    right = min(image.shape[1], bounds[2] + padding)
    bottom = min(image.shape[0], bounds[3] + padding)
    source = Image.fromarray(np.ascontiguousarray(image[top:bottom, left:right]))
    rig = rig or {}
    base = source.copy()
    back_layers = {}
    front_layers = {}
    pivots = {}

    for layer in rig.get("layers", []):
        name = str(layer.get("name", "")).strip()
        polygon = layer.get("polygon", [])
        if not name or len(polygon) < 3:
            continue
        mask = Image.new("L", source.size, 0)
        points = [_normalized_point(point, source.width, source.height) for point in polygon]
        ImageDraw.Draw(mask).polygon(points, fill=255)
        layer_image = source.copy()
        layer_alpha = Image.fromarray(
            np.minimum(np.array(source.getchannel("A")), np.array(mask)).astype(np.uint8)
        )
        layer_image.putalpha(layer_alpha)
        if layer.get("cutout", True):
            base_alpha = np.array(base.getchannel("A"))
            base_alpha[np.array(mask) > 0] = 0
            base.putalpha(Image.fromarray(base_alpha))
        target = back_layers if layer.get("z", "front") == "back" else front_layers
        target[name] = _pil_to_pixmap(layer_image)
        pivots[name] = _normalized_point(
            layer.get("pivot", [0.5, 0.5]), source.width, source.height
        )

    return SpriteArt(
        base=_pil_to_pixmap(base),
        back_layers=back_layers,
        front_layers=front_layers,
        pivots=pivots,
        blink=_build_blink_overlay(source, rig),
    )


class PetSprite(QWidget):
    BASE_WIDTH = 196
    BASE_HEIGHT = 212
    BASE_ART_HEIGHT = 194

    drag_started = Signal(QPoint)
    drag_moved = Signal(QPoint)
    drag_finished = Signal()
    double_clicked = Signal()
    context_requested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.BASE_WIDTH, self.BASE_HEIGHT)
        self.setCursor(Qt.OpenHandCursor)
        self._art = SpriteArt()
        self._state = "idle"
        self._motion = {}
        self._phase = 0
        self._user_scale = 1.0
        self._action = None
        self._action_phase = 0
        self._frame_animations = {}
        self._frame_index = 0
        self._drag_origin = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(90)

    def set_pet(self, art: SpriteArt, motion: dict):
        self._art = art
        self._motion = motion
        self._phase = 0
        self.update()

    def set_frame_animations(self, animations: dict):
        self._frame_animations = animations
        if self._action and self._action not in animations and self._action not in {
            "greet",
            "jump",
            "blink",
        }:
            self._finish_action()
        elif self._action not in animations:
            self._frame_index = 0

    def has_action(self, action: str) -> bool:
        return action in self._frame_animations or action in {"greet", "jump", "blink"}

    @property
    def current_action(self):
        return self._action

    def set_state(self, state: str, motion: dict):
        next_state = state if state in PET_STATES else "idle"
        if next_state != self._state and self._action in self._frame_animations:
            self._finish_action()
        self._state = next_state
        self._motion = motion
        self._phase = 0
        self._timer.setInterval(max(35, int(motion.get("interval_ms", 90))))
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def set_user_scale(self, percent: int):
        self._user_scale = max(0.7, min(1.4, percent / 100.0))
        self.setFixedSize(
            round(self.BASE_WIDTH * self._user_scale),
            round(self.BASE_HEIGHT * self._user_scale),
        )
        self.updateGeometry()
        self.update()

    def play_action(self, action: str):
        if action not in {"greet", "jump", "blink"} and action not in self._frame_animations:
            return
        if self._action == action:
            return
        self._action = action
        self._action_phase = 0
        self._frame_index = 0
        if action in self._frame_animations:
            self._timer.setInterval(self._frame_animations[action]["durations_ms"][0])
        else:
            self._timer.setInterval(45)
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop_action(self):
        if self._action:
            self._finish_action()
            self.update()

    def _finish_action(self):
        self._action = None
        self._action_phase = 0
        self._frame_index = 0
        self._timer.setInterval(max(35, int(self._motion.get("interval_ms", 90))))

    def _advance(self):
        self._phase = (self._phase + 1) % 120
        if self._action in self._frame_animations:
            animation = self._frame_animations[self._action]
            self._frame_index += 1
            if self._frame_index >= len(animation["frames"]):
                if animation.get("loop", False):
                    self._frame_index = 0
                    self._timer.setInterval(animation["durations_ms"][0])
                else:
                    self._finish_action()
            else:
                self._timer.setInterval(animation["durations_ms"][self._frame_index])
            self.update()
            return
        if self._action:
            self._action_phase += 1
            duration = {"greet": 36, "jump": 24, "blink": 10}[self._action]
            if self._action_phase >= duration:
                self._finish_action()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._art.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if (
            self._action in self._frame_animations
            and self._frame_index
            not in self._frame_animations[self._action]["idle_frame_indices"]
        ):
            self._paint_frame_animation(painter)
            return

        wave = math.sin(self._phase * math.pi / 12)
        bob_limit = float(self._motion.get("bob_px", 2))
        tilt_limit = float(self._motion.get("tilt_deg", 0.5))
        scale = float(self._motion.get("scale_pct", 1.0))

        if self._state == "success" and self._phase < 18:
            progress = self._phase / 18
            bob = -math.sin(progress * math.pi) * bob_limit
        else:
            bob = wave * bob_limit
        tilt = wave * tilt_limit * 0.35
        if self._action == "jump":
            progress = min(1.0, self._action_phase / 24)
            bob -= math.sin(progress * math.pi) * 18 * self._user_scale
            tilt += math.sin(progress * math.pi * 2) * 2
        elif self._action == "greet":
            progress = min(1.0, self._action_phase / 36)
            bob -= abs(math.sin(progress * math.pi * 2)) * 2 * self._user_scale
        if self._state == "error":
            painter.setOpacity(0.82)

        target_height = self.BASE_ART_HEIGHT * self._user_scale * scale
        art_scale = target_height / self._art.height
        target_width = self._art.width * art_scale
        x = (self.width() - target_width) / 2
        y = self.height() - target_height - 3 + bob

        # A small breathing deformation keeps the feet planted while the body expands.
        breathe = 1.0 + math.sin(self._phase * math.pi / 20) * 0.006
        painter.translate(x + target_width / 2, y + target_height)
        painter.rotate(tilt)
        painter.scale(art_scale * breathe, art_scale)
        painter.translate(-self._art.width / 2, -self._art.height)

        self._draw_layer(painter, "tail", self._tail_angle(), back=True)
        painter.drawPixmap(0, 0, self._art.base)
        self._draw_layer(painter, "paw", self._paw_angle(), back=False)

        blink_phase = self._phase % 64
        manual_blink = self._action == "blink" and 2 <= self._action_phase <= 8
        if manual_blink or blink_phase in {0, 1, 2}:
            painter.drawPixmap(0, 0, self._art.blink)

    def _paint_frame_animation(self, painter: QPainter):
        animation = self._frame_animations[self._action]
        frame = animation["frames"][self._frame_index]
        reference_height = animation["reference_height"]
        baseline = animation["baseline"]
        frame_scale = self.BASE_ART_HEIGHT * self._user_scale / reference_height
        x = (self.width() - frame.width() * frame_scale) / 2
        y = self.height() - 3 - baseline * frame_scale
        painter.translate(x, y)
        painter.scale(frame_scale, frame_scale)
        painter.drawPixmap(0, 0, frame)

    def _draw_layer(self, painter: QPainter, name: str, angle: float, back: bool):
        layers = self._art.back_layers if back else self._art.front_layers
        layer = layers.get(name)
        pivot = self._art.pivots.get(name)
        if not layer or not pivot:
            return
        painter.save()
        painter.translate(QPointF(*pivot))
        painter.rotate(angle)
        painter.translate(-pivot[0], -pivot[1])
        painter.drawPixmap(0, 0, layer)
        painter.restore()

    def _tail_angle(self):
        speed = 10 if self._state in {"ocr", "translating"} else 17
        amplitude = {
            "translating": 9,
            "success": 13,
            "partial_error": 4,
            "error": 2,
        }.get(self._state, 5)
        angle = math.sin(self._phase * math.pi / speed) * amplitude
        if self._state == "error":
            angle += 7
        if self._action == "jump":
            angle -= math.sin(min(1.0, self._action_phase / 24) * math.pi) * 9
        return angle

    def _paw_angle(self):
        if self._action == "greet":
            progress = min(1.0, self._action_phase / 36)
            envelope = math.sin(progress * math.pi)
            return -4 - math.sin(progress * math.pi * 6) * 8 * envelope
        if self._state == "translating":
            return -3 - abs(math.sin(self._phase * math.pi / 10)) * 5
        if self._state == "speaking":
            return math.sin(self._phase * math.pi / 9) * 4
        return 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            self.drag_started.emit(self._drag_origin)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_origin and event.buttons() & Qt.LeftButton:
            self.drag_moved.emit(event.globalPosition().toPoint())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_origin:
            self._drag_origin = None
            self.setCursor(Qt.OpenHandCursor)
            self.drag_finished.emit()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()


class DesktopPetWindow(QWidget):
    open_main_requested = Signal()
    settings_requested = Signal()
    speak_requested = Signal(str)
    visibility_changed = Signal(bool)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("ManboShot 桌面宠物")

        self._pack = None
        self._state = "idle"
        self._source_text = ""
        self._result_text = ""
        self._pet_top_left = QPoint()
        self._drag_window_origin = QPoint()
        self._drag_cursor_origin = QPoint()
        self._last_drag_cursor = QPoint()
        self._dragging = False
        self._drag_active = False
        self._state_action = None
        self._translation_bubble_allowed = True
        self._sprite_align_right = True

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.hide_bubble)

        self._idle_action_timer = QTimer(self)
        self._idle_action_timer.setSingleShot(True)
        self._idle_action_timer.timeout.connect(self._play_idle_action)

        self._build_ui()
        self.reload_settings(initial=True)

    def _build_ui(self):
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(4)

        self.bubble = QFrame()
        self.bubble.setObjectName("petBubble")
        self.bubble.setFixedWidth(390)
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(16, 13, 16, 14)
        bubble_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.bubble_title = QLabel("ManboShot · 翻译完成")
        self.bubble_title.setObjectName("petBubbleTitle")
        self.bubble_status = QLabel("AI")
        self.bubble_status.setObjectName("petBubbleStatus")
        self.close_bubble_btn = QPushButton("×")
        self.close_bubble_btn.setObjectName("petBubbleClose")
        self.close_bubble_btn.setFixedSize(26, 26)
        self.close_bubble_btn.setToolTip("收起翻译结果")
        self.close_bubble_btn.clicked.connect(self.hide_bubble)
        header.addWidget(self.bubble_title)
        header.addStretch()
        header.addWidget(self.bubble_status)
        header.addWidget(self.close_bubble_btn)

        self.source_label = QLabel()
        self.source_label.setObjectName("petBubbleSource")
        self.source_label.setWordWrap(True)
        self.result_label = QLabel()
        self.result_label.setObjectName("petBubbleResult")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_btn = QPushButton("复制")
        self.copy_btn.setObjectName("petBubbleAction")
        self.copy_btn.clicked.connect(self.copy_result)
        self.speak_btn = QPushButton("朗读原文")
        self.speak_btn.setObjectName("petBubbleAction")
        self.speak_btn.clicked.connect(self.speak_result)
        self.open_btn = QPushButton("查看完整结果")
        self.open_btn.setObjectName("petBubblePrimary")
        self.open_btn.clicked.connect(self._open_main_from_bubble)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.speak_btn)
        actions.addStretch()
        actions.addWidget(self.open_btn)

        bubble_layout.addLayout(header)
        bubble_layout.addWidget(self.source_label)
        bubble_layout.addWidget(self.result_label)
        bubble_layout.addLayout(actions)
        self.bubble.hide()

        self.sprite_row = QHBoxLayout()
        self.sprite_row.setContentsMargins(0, 0, 0, 0)
        self.sprite = PetSprite()
        self.sprite_row.addWidget(self.sprite, 0, Qt.AlignRight)

        self.root_layout.addWidget(self.bubble)
        self.root_layout.addLayout(self.sprite_row)

        self.sprite.drag_started.connect(self._start_drag)
        self.sprite.drag_moved.connect(self._drag_to)
        self.sprite.drag_finished.connect(self._finish_drag)
        self.sprite.double_clicked.connect(self.open_main_requested.emit)
        self.sprite.context_requested.connect(self._show_context_menu)

    def reload_settings(self, initial=False):
        config = load_app_config()
        self._enabled = bool(config.get("PET_ENABLED", True))
        self._bubble_enabled = bool(config.get("PET_BUBBLE_ENABLED", True))
        scale_percent = max(70, min(140, int(config.get("PET_SCALE", 100))))
        self.sprite.set_user_scale(scale_percent)
        selected_id = config.get("PET_ID", "lihua")
        pack = get_pet_pack(selected_id)

        if pack and (not self._pack or self._pack.pet_id != pack.pet_id):
            self._pack = pack
            processing = pack.manifest.get("source_processing", {})
            art = _extract_sprite(
                pack.sprite_path,
                processing,
                pack.manifest.get("rig", {}),
            )
            if art.isNull():
                logger.error("无法加载宠物图片: %s", pack.sprite_path)
            self.sprite.set_pet(art, pack.motion_for("idle"))
            frame_animations = {}
            for animation_name in pack.manifest.get("animations", {}):
                animation = pack.animation_for(animation_name)
                if not animation:
                    logger.warning("忽略无效宠物动作: %s/%s", pack.pet_id, animation_name)
                    continue
                frames = [QPixmap(str(path)) for path in animation["frames"]]
                if any(frame.isNull() for frame in frames):
                    logger.warning("无法加载宠物动作帧: %s/%s", pack.pet_id, animation_name)
                    continue
                frame_animations[animation_name] = dict(animation, frames=frames)
            self.sprite.set_frame_animations(frame_animations)
            self.setWindowTitle(f"ManboShot · {pack.name}")

        self._apply_theme(config.get("THEME", "light"))
        self.set_state("idle")

        if initial:
            saved = config.get("PET_POSITION", {})
            if isinstance(saved, dict) and "x" in saved and "y" in saved:
                self._pet_top_left = QPoint(int(saved["x"]), int(saved["y"]))
            else:
                self._pet_top_left = self._default_position()
        self._pet_top_left = self._clamp_pet_position(self._pet_top_left)
        self._reanchor()

        if self._enabled:
            self.show()
        else:
            self.hide()
        self.visibility_changed.emit(self._enabled)
        self._schedule_idle_action()

    @property
    def can_show_bubble(self) -> bool:
        return bool(self._enabled and self._bubble_enabled)

    def _apply_theme(self, theme_name):
        palette = theme_palette(theme_name)
        self.setStyleSheet(
            f"""
            QFrame#petBubble {{
                background-color: {palette['surface']};
                border: 1px solid {palette['border']};
                border-radius: 8px;
            }}
            QLabel#petBubbleTitle {{
                color: {palette['text']};
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#petBubbleStatus {{
                color: {palette['ai_accent']};
                font-size: 11px;
                font-weight: 700;
            }}
            QLabel#petBubbleSource {{
                color: {palette['muted']};
                font-size: 12px;
                border-bottom: 1px solid {palette['border']};
                padding-bottom: 7px;
            }}
            QLabel#petBubbleResult {{
                color: {palette['text']};
                font-size: 14px;
                font-weight: 500;
                line-height: 1.35;
            }}
            QPushButton#petBubbleClose {{
                background: transparent;
                color: {palette['muted']};
                border: none;
                font-size: 20px;
            }}
            QPushButton#petBubbleClose:hover {{ color: {palette['danger']}; }}
            QPushButton#petBubbleAction {{
                background-color: {palette['surface_subtle']};
                color: {palette['text']};
                border: 1px solid {palette['border']};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton#petBubblePrimary {{
                background-color: {palette['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {palette['primary_hover']}; color: white; }}
            """
        )

    def _default_position(self) -> QPoint:
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        return QPoint(geometry.right() - self.sprite.width() - 24, geometry.bottom() - self.sprite.height() - 12)

    def _screen_for_pet(self, point: QPoint):
        center = point + QPoint(self.sprite.width() // 2, self.sprite.height() // 2)
        screen = QApplication.screenAt(center)
        if screen:
            return screen

        screens = QApplication.screens()
        if not screens:
            return QApplication.primaryScreen()

        def distance_to_screen(candidate):
            rect = candidate.availableGeometry()
            nearest_x = min(max(center.x(), rect.left()), rect.right())
            nearest_y = min(max(center.y(), rect.top()), rect.bottom())
            return (center.x() - nearest_x) ** 2 + (center.y() - nearest_y) ** 2

        return min(screens, key=distance_to_screen)

    def _clamp_pet_position(self, point: QPoint) -> QPoint:
        geometry = self._screen_for_pet(point).availableGeometry()
        x = min(max(point.x(), geometry.left()), geometry.right() - self.sprite.width() + 1)
        y = min(max(point.y(), geometry.top()), geometry.bottom() - self.sprite.height() + 1)
        return QPoint(x, y)

    def _reanchor(self):
        self.adjustSize()
        if self.bubble.isVisible():
            geometry = self._screen_for_pet(self._pet_top_left).availableGeometry()
            room_left = self._pet_top_left.x() - geometry.left()
            room_right = geometry.right() - (self._pet_top_left.x() + self.sprite.width())
            align_right = room_left >= self.width() - self.sprite.width() or room_left >= room_right
            self._sprite_align_right = align_right
            self.sprite_row.setAlignment(self.sprite, Qt.AlignRight if align_right else Qt.AlignLeft)
            if align_right:
                x = self._pet_top_left.x() + self.sprite.width() - self.width()
            else:
                x = self._pet_top_left.x()
            y = self._pet_top_left.y() + self.sprite.height() - self.height()
            x = min(max(x, geometry.left()), geometry.right() - self.width() + 1)
            y = min(max(y, geometry.top()), geometry.bottom() - self.height() + 1)
        else:
            self._sprite_align_right = True
            self.sprite_row.setAlignment(self.sprite, Qt.AlignRight)
            x = self._pet_top_left.x() + self.sprite.width() - self.width()
            y = self._pet_top_left.y() + self.sprite.height() - self.height()
        self.move(x, y)

    def _start_drag(self, cursor_pos: QPoint):
        self._drag_cursor_origin = cursor_pos
        self._last_drag_cursor = cursor_pos
        self._drag_window_origin = self.pos()
        self._dragging = True
        self._drag_active = False
        self._idle_action_timer.stop()

    def _drag_to(self, cursor_pos: QPoint):
        delta = cursor_pos - self._drag_cursor_origin
        if not self._drag_active and delta.manhattanLength() >= 4:
            self._drag_active = True
        if self._drag_active:
            horizontal_delta = cursor_pos.x() - self._last_drag_cursor.x()
            action = "running-right" if horizontal_delta >= 0 else "running-left"
            if abs(horizontal_delta) >= 1 and self.sprite.has_action(action):
                self.sprite.play_action(action)
        self._last_drag_cursor = cursor_pos
        self.move(self._drag_window_origin + delta)
        sprite_offset_x = self.width() - self.sprite.width() if self._sprite_align_right else 0
        self._pet_top_left = QPoint(
            self.x() + sprite_offset_x,
            self.y() + self.height() - self.sprite.height(),
        )

    def _finish_drag(self):
        was_active = self._drag_active
        self._dragging = False
        self._drag_active = False
        if was_active:
            self.sprite.stop_action()
            self._apply_state_action()
        self._pet_top_left = self._clamp_pet_position(self._pet_top_left)
        self._reanchor()
        config = load_app_config()
        config["PET_POSITION"] = {"x": self._pet_top_left.x(), "y": self._pet_top_left.y()}
        save_app_config(config)
        self._schedule_idle_action()

    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu()
        open_action = QAction("打开翻译窗口", menu)
        open_action.triggered.connect(self.open_main_requested.emit)
        lick_paw_action = QAction("舔舔爪子", menu)
        lick_paw_action.setEnabled(self.sprite.has_action("lick_paw"))
        lick_paw_action.triggered.connect(lambda: self.sprite.play_action("lick_paw"))
        blink_action = QAction("眨眨眼", menu)
        blink_action.triggered.connect(lambda: self.sprite.play_action("blink"))
        jump_action = QAction("蹦一下", menu)
        jump_action.triggered.connect(lambda: self.sprite.play_action("jump"))
        hide_bubble_action = QAction("收起结果气泡", menu)
        hide_bubble_action.setEnabled(self.bubble.isVisible())
        hide_bubble_action.triggered.connect(self.hide_bubble)
        settings_action = QAction("桌面宠物设置", menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        hide_action = QAction("隐藏桌面宠物", menu)
        hide_action.triggered.connect(self.disable_pet)
        menu.addAction(open_action)
        menu.addAction(lick_paw_action)
        menu.addAction(blink_action)
        menu.addAction(jump_action)
        menu.addAction(hide_bubble_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(hide_action)
        menu.exec(global_pos)

    def disable_pet(self):
        config = load_app_config()
        config["PET_ENABLED"] = False
        save_app_config(config)
        self.hide()
        self.visibility_changed.emit(False)

    def _schedule_idle_action(self):
        self._idle_action_timer.stop()
        if self._enabled:
            self._idle_action_timer.start(random.randint(12000, 28000))

    def _play_idle_action(self):
        if (
            self._enabled
            and self.isVisible()
            and self._state == "idle"
            and not self._dragging
            and not self.sprite.current_action
            and self.sprite.has_action("lick_paw")
        ):
            self.sprite.play_action("lick_paw")
        self._schedule_idle_action()

    def _apply_state_action(self):
        action = STATE_ACTIONS.get(self._state)
        if action and self.sprite.has_action(action):
            self._state_action = action
            self.sprite.play_action(action)
        elif self._state_action:
            if self.sprite.current_action == self._state_action:
                self.sprite.stop_action()
            self._state_action = None

    def _open_main_from_bubble(self):
        self.hide_bubble()
        self.open_main_requested.emit()

    def set_state(self, state: str, message: str = ""):
        state = state if state in PET_STATES else "idle"
        self._state = state
        motion = self._pack.motion_for(state) if self._pack else {}
        self.sprite.set_state(state, motion)
        self._apply_state_action()
        if message and self._bubble_enabled:
            self.bubble_title.setText("ManboShot")
            self.bubble_status.setText("进行中")
            self.source_label.setText(message)
            self.result_label.setText("")
            self.copy_btn.setEnabled(False)
            self.speak_btn.setEnabled(False)
            self.show_bubble(timeout_ms=0)

    def begin_translation(self, source_text: str, show_bubble: bool = True):
        self._source_text = source_text.strip()
        self._result_text = ""
        self._translation_bubble_allowed = bool(show_bubble)
        self.set_state("translating")
        if self._bubble_enabled and self._translation_bubble_allowed:
            self.bubble_title.setText("ManboShot · 正在翻译")
            self.bubble_status.setText("处理中")
            self.source_label.setText(self._elide(self._source_text, 110))
            self.result_label.setText("正在等待翻译结果…")
            self.copy_btn.setEnabled(False)
            self.speak_btn.setEnabled(False)
            self.show_bubble(timeout_ms=0)
        else:
            self.hide_bubble()

    def update_translation(self, results: dict, source_text: str, show_bubble=None):
        if not self._enabled:
            return
        if show_bubble is not None:
            self._translation_bubble_allowed = bool(show_bubble)
        self._source_text = source_text.strip() or self._source_text
        google_text = (results.get("google", "") or "").strip()
        ai_error = (results.get("doubao_error", "") or "").strip()
        resolved = resolve_translation_state(results)

        if resolved.state == "translating":
            self.set_state("translating")
            if resolved.result_text and self._bubble_enabled and self._translation_bubble_allowed:
                self._result_text = resolved.result_text
                self.result_label.setText(self._elide(resolved.result_text, 260))
                self.bubble_status.setText(resolved.engine_label)
                self.show_bubble(timeout_ms=0)
            return

        if resolved.state in {"success", "partial_error"}:
            state = resolved.state
            self.set_state(state)
            self._result_text = resolved.result_text
            self.bubble_title.setText("ManboShot · 翻译完成")
            self.bubble_status.setText(resolved.engine_label)
            self.source_label.setText(self._elide(self._source_text, 110))
            self.result_label.setText(self._elide(resolved.result_text, 360))
            self.copy_btn.setEnabled(True)
            self.speak_btn.setEnabled(True)
            if self._bubble_enabled and self._translation_bubble_allowed:
                self.show_bubble(timeout_ms=14000)
            QTimer.singleShot(1800, lambda: self.set_state("idle") if self._state == state else None)
            return

        self.set_state("error")
        self._result_text = ""
        self.bubble_title.setText("ManboShot · 翻译失败")
        self.bubble_status.setText("需要重试")
        self.source_label.setText(self._elide(self._source_text, 110))
        error_text = ai_error or google_text.replace("❌", "").strip() or "暂时没有收到翻译结果"
        self.result_label.setText(self._elide(error_text, 220))
        self.copy_btn.setEnabled(False)
        self.speak_btn.setEnabled(False)
        if self._bubble_enabled and self._translation_bubble_allowed:
            self.show_bubble(timeout_ms=10000)

    def show_bubble(self, timeout_ms=14000):
        if not self._bubble_enabled:
            return
        self.bubble.show()
        self._reanchor()
        self.show()
        self.raise_()
        if timeout_ms:
            self._bubble_timer.start(timeout_ms)
        else:
            self._bubble_timer.stop()

    def hide_bubble(self):
        self._bubble_timer.stop()
        self.bubble.hide()
        self._reanchor()

    def copy_result(self):
        if not self._result_text:
            return
        QApplication.clipboard().setText(self._result_text)
        self.copy_btn.setText("已复制")
        QTimer.singleShot(1200, lambda: self.copy_btn.setText("复制"))

    def speak_result(self):
        if self._source_text:
            self.speak_requested.emit(self._source_text)

    @staticmethod
    def _elide(text: str, limit: int) -> str:
        normalized = " ".join(text.split())
        return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"
