from PySide6.QtWidgets import QGraphicsView, QTextEdit
from PySide6.QtGui import QWheelEvent
from PySide6 import QtCore
from PySide6.QtCore import Qt
import re
"""""
class MyLoader(QUiLoader):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createWidget(self, class_name, parent=None, name=""):
        if class_name == "QGraphicsView":
            widget = MyGraphicsView(parent)
            widget.setObjectName(name)
            return widget
        return super().createWidget(class_name, parent, name)
"""""

class MyGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_state = None
        self.setMouseTracking(True)  # 获取鼠标位置
        self.scale_factor = 1.15  # 每次滚动的缩放倍数
        self.min_scale = 0.2      # 最小缩放倍数
        self.max_scale = 5.0      # 最大缩放倍数
        self.current_scale = 1.0  # 当前缩放倍数
        # 以鼠标为中心进行缩放
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def mousePressEvent(self, event):
        if self.parent_state:
            self.parent_state.mouse_press_event(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.parent_state:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.parent_state.update_mouse_pos(scene_pos)
            self.parent_state.mouse_move_event(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parent_state:
            self.parent_state.mouse_release_event(event)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """支持 Ctrl + 滚轮 缩放视图"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 判断滚轮方向
            if event.angleDelta().y() > 0:
                factor = self.scale_factor
            else:
                factor = 1 / self.scale_factor

            # 更新缩放值
            new_scale = self.current_scale * factor
            if self.min_scale <= new_scale <= self.max_scale:
                self.scale(factor, factor)
                self.current_scale = new_scale
            event.accept()
        else:
            # 没按 Ctrl 时执行默认行为（比如滚动视图）
            super().wheelEvent(event)

# 辅助类，将Python的print结果重新定向到Qt控件
class EmittingStr(QtCore.QObject):
    textWritten = QtCore.Signal(str)

    def write(self, text):
        if text:
            # 这里把 \n 替换成真正的换行
            self.textWritten.emit(text)

    def flush(self):
        pass

class CmdTextEdit(QTextEdit):
    def __init__(self, parent_state=None):
        super().__init__()
        self.parent_state = parent_state
        self.setStyleSheet("background-color: white;")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            # 获取整个输入框文本（多行命令）
            cmd = self.toPlainText().strip()
            if cmd:
                if self.parent_state:
                    self.parent_state.handle_command(cmd)
            # 清空输入框
            self.clear()
        else:
            # Shift+Enter 可以换行
            super().keyPressEvent(event)


