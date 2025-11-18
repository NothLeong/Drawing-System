from PySide6 import QtGui
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QMainWindow, QGraphicsScene,
    QGraphicsView, QLabel, QToolButton, QTextEdit,
    QColorDialog, QFileDialog, QCommandLinkButton, QCheckBox, QGraphicsEllipseItem,
    QGraphicsPolygonItem
    )
from PySide6.QtCore import Qt, Slot, QTimer, QPointF
from PySide6.QtGui import QPen, QBrush, QPainter, QImage, QKeyEvent, QPixmap, QColor, QPolygonF

from VectorShape import VectorShape, EllipseShape, PolygonShape
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

        # 设置场景
        canvas_width, canvas_height = 1280, 720
        self.scene = QGraphicsScene(0, 0, canvas_width, canvas_height)
        self.view.setScene(self.scene)

        # 像素画布
        self.canvas_item = RasterCanvas(canvas_width, canvas_height)
        self.scene.addItem(self.canvas_item)
        self.canvas = self.canvas_item

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
        self.current_mode = None
        self.start_pos = None
        self.pen_color = Qt.GlobalColor.black
        self.pen_width = 2
        self.fill = False
        self.line_style = 'solid'

        # 视图特性
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        # 获取按钮并绑定功能
        self.ui.findChild(QCheckBox, "toggle_dash").clicked.connect(lambda: self.set_line_style('dash'))
        self.ui.findChild(QToolButton, "point").clicked.connect(lambda: self.set_mode("点"))
        self.ui.findChild(QToolButton, "line").clicked.connect(lambda: self.set_mode("直线"))
        self.ui.findChild(QToolButton, "polygon").clicked.connect(lambda: self.set_mode("多边形"))
        self.ui.findChild(QToolButton, "ellipse").clicked.connect(lambda: self.set_mode("椭圆"))
        self.ui.findChild(QToolButton, "circle").clicked.connect(lambda: self.set_mode("圆"))
        self.ui.findChild(QToolButton, "drag_and_drop").clicked.connect(lambda: self.set_mode("拖放"))
        self.ui.findChild(QToolButton, "move").clicked.connect(lambda: self.set_mode("平移"))
        self.ui.findChild(QToolButton, "rotate").clicked.connect(lambda: self.set_mode("旋转"))
        self.ui.findChild(QToolButton, "color_choose").clicked.connect(lambda: self.choose_color())
        self.ui.findChild(QToolButton, "fill_toggle").clicked.connect(lambda: self.set_mode("填充"))
        self.ui.findChild(QToolButton, "save").clicked.connect(lambda: self.save_scene())

        # 当前选中VectorShape
        self.current_shape = None

        self.drag_offset = 0
        self.last_mouse_for_rotate = None

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

    def set_line_style(self, style:str):
        if style == self.line_style:
            self.line_style = 'solid'
        else: self.line_style = style
        print(f"当前线形: {self.line_style}")

    def save_scene(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存图形", "", "PNG Files (*.png);;JPEG Files (*.jpg)")
        if file_path:
            from os import makedirs, path
            # 确保目录存在
            makedirs(path.dirname(file_path), exist_ok=True)
            if self.canvas.save(file_path):
                print(f"图片已保存至 {file_path}")
            else:
                print(f"保存失败: {file_path}")

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
                        item = self.scene.addEllipse(x, y, 2, 2,
                                              pen=QPen(self.pen_color, self.pen_width),
                                              brush=QBrush(self.pen_color if self.fill else Qt.BrushStyle.NoBrush))
                        item.setData(0, "user")
                    elif parts[1] == "line":
                        x1, y1 = map(float, parts[3].strip("()").split(","))
                        x2, y2 = map(float, parts[5].strip("()").split(","))
                        item = self.scene.addLine(x1, y1, x2, y2, pen=QPen(self.pen_color, self.pen_width))
                        item.setData(0, "user")
                    elif parts[1] == "circle":
                        x, y = map(float, parts[3].strip("()").split(","))
                        r_index = parts.index("-r")
                        radius = float(parts[r_index + 1])
                        item = self.scene.addEllipse(x - radius, y - radius, radius * 2, radius * 2,
                                              pen=QPen(self.pen_color, self.pen_width),
                                              brush=QBrush(self.pen_color if self.fill else Qt.BrushStyle.NoBrush))
                        item.setData(0, "user")
                    elif parts[1] == "ellipse":
                        x, y = map(float, parts[3].strip("()").split(","))
                        a_index = parts.index("-a")
                        a = float(parts[a_index + 1])
                        b_index = parts.index("-b")
                        b = float(parts[b_index + 1])
                        angle = 0.0
                        if "-angle" in parts:
                            angle_index = parts.index("-angle")
                            angle = float(parts[angle_index + 1])

                        # 用 QGraphicsEllipseItem 创建椭圆，先生成未旋转的矩形
                        ellipse_item = QGraphicsEllipseItem(x - a, y - b, 2 * a, 2 * b)
                        ellipse_item.setPen(QPen(self.pen_color, self.pen_width))
                        if self.fill:
                            ellipse_item.setBrush(QBrush(self.pen_color))

                        # 设置旋转中心为椭圆中心
                        ellipse_item.setTransformOriginPoint(QPointF(x, y))
                        ellipse_item.setRotation(angle)

                        ellipse_item.setData(0, "user")
                        self.scene.addItem(ellipse_item)

                    elif parts[1] == "polygon":
                        points = []
                        for p in parts[2:]:
                            if p.startswith("(") and p.endswith(")"):
                                x, y = map(float, p.strip("()").split(","))
                                points.append(QPointF(x, y))
                            else:
                                break

                        polygon_item = QGraphicsPolygonItem(QPolygonF(points))
                        polygon_item.setPen(QPen(self.pen_color, self.pen_width))
                        polygon_item.setData(0, "user")
                        self.scene.addItem(polygon_item)

                elif parts[0] == "clear":
                    # 清理scene上的图元
                    for item in self.scene.items():
                        if item.data(0) == "user":
                            self.scene.removeItem(item)
                    # 清理画布
                    self.canvas.clear_temp()
                    self.canvas.image.fill(self.canvas.bg_color)
                    self.canvas.update_pixmap()
            except Exception as e:
                print(f"指令解析错误: {e}")

    @Slot()
    def set_mode(self, shape_name):
        self.current_mode = shape_name
        print(f"当前模式：{shape_name}")
        if self.current_mode == "多边形":
            print("左键选取端点，右键确定最后一个端点并画出最终的多边形")

    @Slot()
    def mouse_press_event(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.current_shape is not None and self.current_shape.type == "Polygon":
            self.start_pos = self.view.mapToScene(event.position().toPoint())
            self.current_shape.points.append(self.start_pos)
            self.canvas.draw_polygon(self.current_shape, "image")
            self.canvas.shapes.append(self.current_shape)
            self.current_shape = None
        elif event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.view.mapToScene(event.position().toPoint())

            # 画图形
            if self.current_mode in ("圆", "椭圆", "直线"):
                return
            elif self.current_mode == "多边形":
                # 将鼠标点击位置转换到 image/scene 坐标
                if self.current_shape is None:
                    self.current_shape = PolygonShape([self.start_pos], self.pen_color)
                else:
                    self.current_shape.points.append(self.start_pos)

                # 临时绘制已有顶点连线
                self.canvas.draw_polygon(self.current_shape, "temp")

            if self.current_mode == "平移":
                # 记录平移起点（scene 坐标）
                self.pan_start = self.view.mapToScene(event.position().toPoint())
                return
            elif self.current_mode == "点":
                radius = 3  # 半径，可调整大小
                cx, cy = int(self.start_pos.x()), int(self.start_pos.y())
                W, H = self.canvas.image.width(), self.canvas.image.height()

                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if dx * dx + dy * dy <= radius * radius:  # 圆形判断
                            x, y = cx + dx, cy + dy
                            if 0 <= x < W and 0 <= y < H:
                                self.canvas.image.setPixelColor(x, y, self.pen_color)

                self.canvas.update_pixmap()

                self.canvas.update_pixmap()
            elif self.current_mode == "填充":
                print(f"在{self.start_pos}处进行填充")
                self.canvas.fill_at_point(self.start_pos, self.pen_color)
            elif self.current_mode == "旋转":
                self.last_mouse_for_rotate = None
                self.current_shape = self.canvas.find_shape_at_image_point(self.start_pos)
                if self.current_shape is not None:
                    print(f"对 {self.start_pos} 处的图形 {self.current_shape.type} 进行旋转")
                else:
                    print(f"在 {self.start_pos} 处没有找到可旋转的图形")
                return
            elif self.current_mode == "拖放":
                self.current_shape = self.canvas.find_shape_at_image_point(self.start_pos)
                if self.current_shape is not None:
                    # 记录鼠标点击点到图形中心的偏移
                    c = self.current_shape.get_centre()
                    self.drag_offset = QPointF(self.start_pos.x() - c.x(),
                                               self.start_pos.y() - c.y())
                return

            self.start_pos = None

    @Slot()
    def mouse_move_event(self, event):
        end_pos = self.view.mapToScene(event.position().toPoint())
        pen = QPen(self.pen_color, self.pen_width)
        brush = QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)

        # 实时更新鼠标坐标
        self.update_mouse_pos(end_pos)

        if self.current_mode == "平移" and hasattr(self, "pan_start"):
            # 当前鼠标位置（scene 坐标）
            current_pos = self.view.mapToScene(event.position().toPoint())
            # 计算位移增量
            dx = current_pos.x() - self.pan_start.x()
            dy = current_pos.y() - self.pan_start.y()
            # 平移视图
            self.view.translate(-dx, -dy)  # 负号因为 QGraphicsView 移动方向与鼠标相反
            # 更新起点
            self.pan_start = current_pos
            return

        if self.start_pos and self.current_mode == "旋转":
            prev_pos = getattr(self, 'last_mouse_for_rotate', None)
            if prev_pos is None:
                prev_pos = self.start_pos

            from math import degrees, atan2
            c = self.current_shape.get_centre()
            dx0, dy0 = prev_pos.x() - c.x(), prev_pos.y() - c.y()
            dx1, dy1 = end_pos.x() - c.x(), end_pos.y() - c.y()
            delta_angle = degrees(atan2(dy1, dx1) - atan2(dy0, dx0))

            # 增量旋转
            self.canvas.rotate(delta_angle, self.current_shape)

            # 更新上一次位置
            self.last_mouse_for_rotate = end_pos


        elif self.start_pos and self.current_mode == "拖放":
            self.canvas.clear_temp()
            if self.current_shape is not None:
                # 计算图形的新中心 = 鼠标位置 - 偏移
                new_centre = QPointF(end_pos.x() - self.drag_offset.x(),
                                     end_pos.y() - self.drag_offset.y())
                dx = new_centre.x() - self.current_shape.get_centre().x()
                dy = new_centre.y() - self.current_shape.get_centre().y()
                self.canvas.drag_and_drop(dx, dy, self.current_shape)

        elif self.start_pos and self.current_mode == "直线":
            # scene 坐标 -> image 坐标
            x0, y0 = self.canvas.scene_to_image(self.start_pos)
            x1, y1 = self.canvas.scene_to_image(end_pos)

            # 在 temp 层绘制预览线
            self.canvas.draw_temp_line(x0, y0, x1, y1, self.pen_color, self.line_style)
            # canvas.draw_temp_line 已经在内部调用 update_pixmap()

        if self.start_pos and self.current_mode == "椭圆":
            # 在temp层画椭圆
            from VectorShape import EllipseShape
            ellipse = EllipseShape(self.start_pos, end_pos, self.pen_color, None, self.line_style)
            self.canvas.draw_ellipse(ellipse, 'temp')

        elif self.current_mode == "多边形" and self.current_shape is not None:
            temp_points = self.current_shape.points + [end_pos]
            # 绘制临时悬浮线（只画线，不写入 image）
            # 悬浮线闭合
            if len(self.current_shape.points) >= 2:
                temp_points += [self.current_shape.points[0]]
            self.canvas.draw_polygon_points(temp_points, self.current_shape.border_color)


        if self.start_pos and self.current_mode == "圆":
            r = calc_radius(self.start_pos, end_pos)
            self.canvas.draw_temp_circle(self.start_pos, r, self.pen_color, self.line_style)

    @Slot()
    def mouse_release_event(self, event):
        if not self.start_pos:
            return

        end_pos = self.view.mapToScene(event.position().toPoint())
        pen = QPen(self.pen_color, self.pen_width)
        brush = QBrush(self.pen_color) if self.fill else QBrush(Qt.BrushStyle.NoBrush)

        if self.current_mode == "平移" and hasattr(self, "pan_start"):
            # 松开鼠标，结束平移
            del self.pan_start
            return

        # 删除预览线
        if hasattr(self, "temp_item") and self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None

        if self.current_mode == "直线":
            x0, y0 = self.canvas.scene_to_image(self.start_pos)
            x1, y1 = self.canvas.scene_to_image(end_pos)

            # 直接写入主图（会扩展并 update）
            self.canvas.draw_line_to_image(x0, y0, x1, y1, self.pen_color, self.line_style)

        if self.current_mode == "椭圆":
            # 添加正式椭圆
            ellipse = EllipseShape(self.start_pos, end_pos, self.pen_color, self.line_style)
            self.canvas.shapes.append(ellipse)
            self.canvas.draw_ellipse(ellipse, 'image')

        if self.current_mode == "圆":
            r = calc_radius(self.start_pos, end_pos)
            self.canvas.draw_circle_to_image(self.start_pos, r, self.pen_color, self.line_style)

        if self.current_mode == "矩形":
            p_start, p_end = self.start_pos, end_pos
            rect = make_rect(p_start, p_end)
            self.scene.addRect(rect[0], rect[1], rect[2], rect[3], pen, brush)

        if self.current_mode == "旋转" or self.current_mode == "拖放":
            self.canvas.redraw()  # 将image层清空，根据矢量图记录来作画

        self.start_pos = None
        self.drag_offset = None
        self.current_shape = None

    def update_mouse_pos(self, scene_pos):
        """更新 label 显示鼠标坐标"""
        if self.pos_label:
            self.pos_label.setText(f"({scene_pos.x():.1f}, {scene_pos.y():.1f})")




