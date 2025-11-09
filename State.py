from PySide6 import QtGui
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene,
    QGraphicsView, QLabel, QToolButton, QTextEdit,
    QColorDialog, QFileDialog, QCommandLinkButton
    )
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QPen, QBrush, QPainter, QImage, QKeyEvent, QPixmap
from module import MyGraphicsView, CmdTextEdit, EmittingStr
from tool import *
import sys

class State(QMainWindow):
    def __init__(self):
        super().__init__()

        # 加载 UI
        self.ui = QUiLoader().load("UI/main.ui")

        # 将打印定向到指令输出部件
        self.cmd_out = self.ui.findChild(QTextEdit, "cmd_out")
        self.cmd_out.setReadOnly(True)
        sys.stdout = EmittingStr()
        sys.stdout.textWritten.connect(self.append_output)

        # 找到原来的 QGraphicsView
        old_view = self.ui.findChild(QGraphicsView, "graphicsView")
        parent_layout = old_view.parentWidget().layout()

        # 创建自定义 QGraphicsView，并替换原来的
        self.view = MyGraphicsView()
        self.view.setObjectName("graphicsView")
        self.view.parent_state = self

        # 删除旧 view 并加入 layout
        old_view.setParent(None)
        parent_layout.addWidget(self.view)

        # 设置场景并白色背景
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(Qt.GlobalColor.white))
        self.view.setScene(self.scene)
        self.temp_item = None  # 临时预览图形

        # 替换指令输入框为自定义类
        old_cmd_in = self.ui.findChild(QTextEdit, "cmd_in")
        # 获取父控件和布局
        parent = old_cmd_in.parentWidget()
        layout = parent.layout()
        # 创建自定义 cmd_in
        self.cmd_in = CmdTextEdit(parent_state=self)
        self.cmd_in.setObjectName("cmd_in")
        self.cmd_in.setFixedSize(old_cmd_in.size())  # 保持大小
        self.cmd_in.setStyleSheet("background-color: white;")
        # 替换
        index = layout.indexOf(old_cmd_in)
        layout.insertWidget(index, self.cmd_in)
        old_cmd_in.setParent(None)  # 移除原控件

        # 绑定Enter部件敲击到cmd输入
        self.ui.findChild(QCommandLinkButton, "enter").clicked.connect(lambda: self.click_enter())

        # 获取坐标显示的 QLabel
        self.pos_label = self.ui.findChild(QLabel, "posLabel")
        # 将 label 设置为 view 的子控件
        self.pos_label.setParent(self.view)
        self.pos_label.raise_()  # 确保覆盖在上层
        self.pos_label.setFixedSize(80, 20)
        self.pos_label.show()

        # 使用定时器保持 label 在右下角
        self._update_label_position()
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_label_position)
        self.timer.start(50)  # 每 50ms 更新位置

        # 画圆时半径显示
        self.radius_label = QLabel(self.view)
        self.radius_label.setStyleSheet("background-color: rgba(255,255,255,200); border:1px solid gray;")
        self.radius_label.setFixedSize(60, 20)
        self.radius_label.hide()  # 默认隐藏

        # 初始化绘图参数
        self.current_shape = None
        self.start_pos = None
        self.pen_color = Qt.GlobalColor.black
        self.pen_width = 2
        self.fill = False

        # 视图特性
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        # 获取按钮并绑定功能
        self.ui.findChild(QToolButton, "point").clicked.connect(lambda: self.set_shape("点"))
        self.ui.findChild(QToolButton, "line").clicked.connect(lambda: self.set_shape("直线"))
        self.ui.findChild(QToolButton, "rectangle").clicked.connect(lambda: self.set_shape("矩形"))
        self.ui.findChild(QToolButton, "ellipse").clicked.connect(lambda: self.set_shape("椭圆"))
        self.ui.findChild(QToolButton, "circle").clicked.connect(lambda: self.set_shape("圆"))
        self.ui.findChild(QToolButton, "move").clicked.connect(lambda: self.set_shape("移动"))
        self.ui.findChild(QToolButton, "color_choose").clicked.connect(lambda: self.choose_color())
        self.ui.findChild(QToolButton, "fill_toggle").clicked.connect(lambda: self.toggle_fill())
        self.ui.findChild(QToolButton, "save").clicked.connect(lambda: self.save_scene())

        self.width = 800
        self.height = 600
        self.canvas = QImage(self.width, self.height, QImage.Format.Format_RGB32)
        self.canvas.fill(Qt.GlobalColor.white)

        self.canvas_item = self.scene.addPixmap(QPixmap.fromImage(self.canvas))

    def append_output(self, text):
        cursor = self.cmd_out.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.cmd_out.setTextCursor(cursor)
        self.cmd_out.ensureCursorVisible()

    def _update_label_position(self):
        """保持坐标标签在画布右下角"""
        if self.pos_label and self.view:
            margin = 10
            w = self.view.width()
            h = self.view.height()
            lw = self.pos_label.width()
            lh = self.pos_label.height()
            self.pos_label.move(w - lw - margin, h - lh - margin)

    def click_enter(self):
        # 创建一个回车键的按下事件
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Return, Qt.KeyboardModifiers())
        # 调用 cmd_in 的 keyPressEvent
        self.cmd_in.keyPressEvent(event)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.pen_color = color
        print(f"当前颜色: {self.pen_color.name()}")

    def toggle_fill(self):
        self.fill = not self.fill
        state = "开启" if self.fill else "关闭"
        print(f"填充模式：{state}")

    def save_scene(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存图形", "", "PNG Files (*.png);;JPEG Files (*.jpg)")
        if file_path:
            # 使用 QImage + QPainter 渲染
            rect = self.scene.itemsBoundingRect()
            image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            self.scene.render(painter)
            painter.end()
            image.save(file_path)
            print(f"图片已保存至{file_path}")

    def handle_command(self, cmd: str):
        """解析并执行多行命令"""
        lines = cmd.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            print(f"执行命令: {line}")
            parts = line.split()  # <--- 用 line 而不是 cmd
            try:
                if parts[0] == "draw":
                    if parts[1] == "point":
                        x, y = map(float, parts[-1].strip("()").split(","))
                        self.scene.addEllipse(x, y, 2, 2,
                                              pen=QPen(self.pen_color, self.pen_width),
                                              brush=QBrush(self.pen_color if self.fill else Qt.BrushStyle.NoBrush))
                    elif parts[1] == "line":
                        x1, y1 = map(float, parts[3].strip("()").split(","))
                        x2, y2 = map(float, parts[5].strip("()").split(","))
                        self.scene.addLine(x1, y1, x2, y2, pen=QPen(self.pen_color, self.pen_width))
                    elif parts[1] == "circle":
                        x, y = map(float, parts[3].strip("()").split(","))
                        r_index = parts.index("-r")
                        radius = float(parts[r_index + 1])
                        self.scene.addEllipse(x - radius, y - radius, radius * 2, radius * 2,
                                              pen=QPen(self.pen_color, self.pen_width),
                                              brush=QBrush(self.pen_color if self.fill else Qt.BrushStyle.NoBrush))
                elif parts[0] == "clear":
                    self.scene.clear()
            except Exception as e:
                print(f"指令解析错误: {e}")

    @Slot()
    def set_shape(self, shape_name):
        self.current_shape = shape_name
        print(f"当前形状：{shape_name}")

    @Slot()
    def mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.view.mapToScene(event.position().toPoint())

            # 画图形
            if self.current_shape in ("圆", "椭圆", "矩形", "直线"):
                self.temp_item = None
                return

            # 移动画布模式
            if self.current_shape == "移动":
                item = self.scene.itemAt(self.start_pos, self.view.transform())
                if item:
                    self.selected_item = item
                    self.last_mouse_pos = self.start_pos
                else:
                    self.selected_item = None
                return

            elif self.current_shape == "点":
                self.scene.addEllipse(
                    self.start_pos.x(), self.start_pos.y(), 2, 2,
                    QPen(self.pen_color, self.pen_width),
                    QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)
                )
                self.start_pos = None

    @Slot()
    def mouse_move_event(self, event):
        end_pos = self.view.mapToScene(event.position().toPoint())
        pen = QPen(self.pen_color, self.pen_width)
        brush = QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)

        # 实时更新鼠标坐标
        scene_pos = end_pos
        self.update_mouse_pos(scene_pos)

        if self.current_shape == "移动" and hasattr(self, "selected_item") and self.selected_item:
            dx = scene_pos.x() - self.last_mouse_pos.x()
            dy = scene_pos.y() - self.last_mouse_pos.y()
            self.selected_item.moveBy(dx, dy)
            self.last_mouse_pos = scene_pos
            return

        # 判断是否需要作图
        if self.start_pos and self.current_shape == "直线":
            if hasattr(self, "temp_pixels"):
                self.clear_temp_layer()  # 清空上次画的预览像素
            draw_line_bresenham(self, self.start_pos.x(), self.start_pos.y(),
                end_pos.x(), end_pos.y(), self.pen_color
            )
            self.refresh_canvas()

        if self.start_pos and self.current_shape == "椭圆":
            # 删除临时圆
            if hasattr(self, "temp_item") and self.temp_item:
                self.scene.removeItem(self.temp_item)

            # 使用addEllipse画椭圆，用到矩形框
            p_start, p_end = self.start_pos, end_pos
            rect = make_rect(p_start,p_end)
            self.temp_item = self.scene.addEllipse(rect[0], rect[1], rect[2], rect[3], pen, brush)

        if self.current_shape == "矩形":
            if self.start_pos and self.current_shape == "矩形":
                if hasattr(self, "temp_item") and self.temp_item:
                    self.scene.removeItem(self.temp_item)

                p_start, p_end = self.start_pos, end_pos
                rect = make_rect(p_start, p_end)
                self.temp_item = self.scene.addRect(rect[0], rect[1], rect[2], rect[3], pen, brush)

        if self.start_pos and self.current_shape == "圆":
            pen.setStyle(Qt.PenStyle.DashLine)  # 虚线
            # 删除上一个临时圆
            if self.temp_item:
                self.scene.removeItem(self.temp_item)

            # 计算半径
            dx = end_pos.x() - self.start_pos.x()
            dy = end_pos.y() - self.start_pos.y()
            radius = (dx ** 2 + dy ** 2) ** 0.5

            # 更新半径标签
            self.radius_label.setText(f"{radius:.1f}")
            view_pos = self.view.mapFromScene(end_pos)
            self.radius_label.move(view_pos.x() + 10, view_pos.y() + 10)
            self.radius_label.show()

            # 绘制临时圆
            self.temp_item = self.scene.addEllipse(
                self.start_pos.x() - radius,
                self.start_pos.y() - radius,
                radius * 2,
                radius * 2,
                pen,
                QBrush(Qt.BrushStyle.NoBrush)  # 临时圆不填充
            )

    @Slot()
    def mouse_release_event(self, event):
        if not self.start_pos:
            return

        end_pos = self.view.mapToScene(event.position().toPoint())
        pen = QPen(self.pen_color, self.pen_width)
        brush = QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)

        if self.current_shape == "移动" and hasattr(self, "selected_item") and self.selected_item:
            self.selected_item = None
            self.start_pos = None
            return

        # 删除预览线
        if hasattr(self, "temp_item") and self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None

        if self.current_shape == "直线":
            # 添加正式线条
            draw_line_bresenham(self, self.start_pos.x(), self.start_pos.y(),
                end_pos.x(), end_pos.y(), self.pen_color
            )
            self.refresh_canvas()

        if self.current_shape == "椭圆":
            # 添加正式椭圆
            # 使用addEllipse画椭圆，用到矩形框
            p_start, p_end = self.start_pos, end_pos
            rect = make_rect(p_start,p_end)
            self.scene.addEllipse(rect[0], rect[1], rect[2], rect[3], pen, brush)

        if self.current_shape == "圆":
            # 删除临时圆
            if self.temp_item:
                self.scene.removeItem(self.temp_item)
                self.temp_item = None

            self.radius_label.hide()  # 关闭半径显示

            # 计算半径
            dx = end_pos.x() - self.start_pos.x()
            dy = end_pos.y() - self.start_pos.y()
            radius = (dx ** 2 + dy ** 2) ** 0.5

            # 添加正式圆
            self.scene.addEllipse(
                self.start_pos.x() - radius,
                self.start_pos.y() - radius,
                radius * 2,
                radius * 2,
                pen,
                brush
            )

            self.start_pos = None
            return

        if self.current_shape == "矩形":
            p_start, p_end = self.start_pos, end_pos
            rect = make_rect(p_start, p_end)
            self.scene.addRect(rect[0], rect[1], rect[2], rect[3], pen, brush)
        self.start_pos = None

    def update_mouse_pos(self, scene_pos):
        """更新 label 显示鼠标坐标"""
        if self.pos_label:
            self.pos_label.setText(f"({scene_pos.x():.1f}, {scene_pos.y():.1f})")

    def refresh_canvas(self):
        """更新 QGraphicsScene 显示"""
        self.canvas_item.setPixmap(QPixmap.fromImage(self.canvas))
        self.scene.update()

    def clear_canvas(self):
        self.canvas.fill(Qt.GlobalColor.white)
        self.refresh_canvas()

