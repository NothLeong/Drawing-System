from PySide6 import QtGui
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene,
    QGraphicsView, QLabel, QToolButton, QTextEdit,
    QColorDialog, QFileDialog, QCommandLinkButton
    )
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QPen, QBrush, QPainter, QImage, QKeyEvent, QPixmap, QColor
from module import MyGraphicsView, RasterCanvas, CmdTextEdit, EmittingStr
from tool import make_rect, calc_radius
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
        self.ui.findChild(QToolButton, "point").clicked.connect(lambda: self.set_mode("点"))
        self.ui.findChild(QToolButton, "line").clicked.connect(lambda: self.set_mode("直线"))
        self.ui.findChild(QToolButton, "rectangle").clicked.connect(lambda: self.set_mode("矩形"))
        self.ui.findChild(QToolButton, "ellipse").clicked.connect(lambda: self.set_mode("椭圆"))
        self.ui.findChild(QToolButton, "circle").clicked.connect(lambda: self.set_mode("圆"))
        self.ui.findChild(QToolButton, "move").clicked.connect(lambda: self.set_mode("移动"))
        self.ui.findChild(QToolButton, "color_choose").clicked.connect(lambda: self.choose_color())
        self.ui.findChild(QToolButton, "fill_toggle").clicked.connect(lambda: self.set_mode("填充"))
        self.ui.findChild(QToolButton, "save").clicked.connect(lambda: self.save_scene())

        # 像素画布
        self.canvas_item = RasterCanvas(800, 600)
        self.scene.addItem(self.canvas_item)
        self.canvas = self.canvas_item

    def _update_label_position(self):
        """保持坐标标签在画布右下角"""
        if self.pos_label and self.view:
            margin = 10
            w = self.view.width()
            h = self.view.height()
            lw = self.pos_label.width()
            lh = self.pos_label.height()
            self.pos_label.move(w - lw - margin, h - lh - margin)

    def append_output(self, text):
        cursor = self.cmd_out.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.cmd_out.setTextCursor(cursor)
        self.cmd_out.ensureCursorVisible()

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

    def save_scene(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存图形", "", "PNG Files (*.png);;JPEG Files (*.jpg)")
        if file_path:
            self.canvas.save(file_path)
            print(f"图片已保存至{file_path}")

    def handle_command(self, cmd: str):
        pass
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
    def set_mode(self, shape_name):
        self.current_shape = shape_name
        print(f"当前模式：{shape_name}")

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
            elif self.current_shape == "填充":
                print(f"在{self.start_pos}处进行填充")
                self.canvas.fill_at_point(self.start_pos, self.pen_color)

            self.start_pos = None

    @Slot()
    def mouse_move_event(self, event):
        end_pos = self.view.mapToScene(event.position().toPoint())
        pen = QPen(self.pen_color, self.pen_width)
        brush = QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)

        # 实时更新鼠标坐标
        self.update_mouse_pos(end_pos)

        if self.current_shape == "移动" and hasattr(self, "selected_item") and self.selected_item:
            dx = end_pos.x() - self.last_mouse_pos.x()
            dy = end_pos.y() - self.last_mouse_pos.y()
            self.selected_item.moveBy(dx, dy)
            self.last_mouse_pos = end_pos
            return

        # 判断是否需要作图
        if self.start_pos and self.current_shape == "直线":
            # 清空上一帧预览
            self.canvas.clear_temp()

            # scene 坐标 -> image 坐标
            x0, y0 = self.canvas.scene_to_image(self.start_pos)
            x1, y1 = self.canvas.scene_to_image(end_pos)

            # 在 temp 层绘制预览线
            self.canvas.draw_temp_line(x0, y0, x1, y1, self.pen_color)
            # canvas.draw_temp_line 已经在内部调用 update_pixmap()

        if self.start_pos and self.current_shape == "椭圆":
            # 清空上一帧预览
            self.canvas.clear_temp()

            # 在temp层画椭圆
            self.canvas.draw_temp_ellipse(self.start_pos, end_pos, self.pen_color)

        if self.current_shape == "矩形":
            if self.start_pos and self.current_shape == "矩形":
                if hasattr(self, "temp_item") and self.temp_item:
                    self.scene.removeItem(self.temp_item)

                p_start, p_end = self.start_pos, end_pos
                rect = make_rect(p_start, p_end)
                self.temp_item = self.scene.addRect(rect[0], rect[1], rect[2], rect[3], pen, brush)

        if self.start_pos and self.current_shape == "圆":
            self.canvas.clear_temp()

            r = calc_radius(self.start_pos, end_pos)
            self.canvas.draw_temp_circle(self.start_pos, r, self.pen_color)

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
            x0, y0 = self.canvas.scene_to_image(self.start_pos)
            x1, y1 = self.canvas.scene_to_image(end_pos)

            # 直接写入主图（会扩展并 update）
            self.canvas.draw_line_to_image(x0, y0, x1, y1, self.pen_color)

            # 清空临时层（若还残留）
            self.canvas.clear_temp()
            self.canvas.update_pixmap()

        if self.current_shape == "椭圆":
            # 添加正式椭圆
            self.canvas.draw_ellipse_to_image(self.start_pos, end_pos, self.pen_color)

            self.canvas.clear_temp()
            self.canvas.update_pixmap()

        if self.current_shape == "圆":
            r = calc_radius(self.start_pos, end_pos)
            self.canvas.draw_circle_to_image(self.start_pos, r, self.pen_color)

            self.canvas.clear_temp()
            self.canvas.update_pixmap()

        if self.current_shape == "矩形":
            p_start, p_end = self.start_pos, end_pos
            rect = make_rect(p_start, p_end)
            self.scene.addRect(rect[0], rect[1], rect[2], rect[3], pen, brush)

        self.start_pos = None

    def update_mouse_pos(self, scene_pos):
        """更新 label 显示鼠标坐标"""
        if self.pos_label:
            self.pos_label.setText(f"({scene_pos.x():.1f}, {scene_pos.y():.1f})")

    def clear_canvas(self):
        """清空主画布"""
        self.canvas.image.fill(Qt.white)
        self.canvas.clear_temp()
        self.canvas.update_pixmap()

