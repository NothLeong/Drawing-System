from PySide6.QtWidgets import QGraphicsView, QTextEdit, QGraphicsPixmapItem
from PySide6.QtGui import QWheelEvent, QImage, QPixmap, QPainter, QColor
from PySide6 import QtCore
from PySide6.QtCore import Qt, QPointF
import re
from VectorShape import *
from tool import draw_line_bresenham

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
        self.scale_factor = 1.15     # 每次滚动的缩放倍数
        self.min_scale = 0.2         # 最小缩放倍数
        self.max_scale = 5.0         # 最大缩放倍数
        self.current_scale = 1.0     # 当前缩放倍数
        self._pan_active = False     # 是否正在平移视图
        self._last_mouse_pos = None  # 平移的上次鼠标位置

        # 以鼠标为中心进行缩放
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # 平滑缩放
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)

    def mousePressEvent(self, event):
        if self.parent_state and self.parent_state.current_mode == "平移" and event.button() == Qt.MouseButton.LeftButton:
            self._pan_active = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.parent_state:
            self.parent_state.mouse_press_event(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_active and self._last_mouse_pos:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()

            # 反向更新滚动条实现平移
            hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
        elif self.parent_state:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.parent_state.update_mouse_pos(scene_pos)
            self.parent_state.mouse_move_event(event)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_active:
            self._pan_active = False
            self._last_mouse_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self.parent_state:
            self.parent_state.mouse_release_event(event)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = self.scale_factor if event.angleDelta().y() > 0 else 1 / self.scale_factor

            if self.parent_state is None:
                super().wheelEvent(event)
                return

            canvas = self.parent_state.canvas
            view_size = self.viewport().size()

            # 计算缩放后的比例
            new_scale = self.current_scale * factor

            # 最小缩放：不能比 view 小
            min_scale_w = view_size.width() / canvas.image.width()
            min_scale_h = view_size.height() / canvas.image.height()
            min_scale = min(min_scale_w, min_scale_h)

            # 最大缩放：固定值，例如 5
            max_scale = 5.0

            # 限制 new_scale
            if new_scale < min_scale:
                factor = min_scale / self.current_scale
                new_scale = min_scale
            elif new_scale > max_scale:
                factor = max_scale / self.current_scale
                new_scale = max_scale

            # 应用缩放
            self.scale(factor, factor)
            self.current_scale = new_scale
            event.accept()
        else:
            super().wheelEvent(event)

    def fit_scene_to_view(self):
        if self.scene() is None:
            return
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.current_scale = 1.0

class RasterCanvas(QGraphicsPixmapItem):
    """像素画布 + 临时层（预览），支持自动扩展 & 合并显示"""

    def __init__(self, width=800, height=600, bg_color=QColor('white')):
        super().__init__()
        # 主图和临时层都用 ARGB32（方便合成透明）
        self.image = QImage(width, height, QImage.Format.Format_ARGB32)
        self.image.fill(bg_color)
        self.temp = QImage(width, height, QImage.Format.Format_ARGB32)
        self.temp.fill(Qt.transparent)

        # 画布扩展
        self.offset_x = 0
        self.offset_y = 0

        self.shapes = []  # 矢量图集合

        self.bg_color = bg_color
        self.setPixmap(QPixmap.fromImage(self.combined_image()))
        self.setPos(0, 0)  # scene 中放置的位置

    # ---------- 合并用的临时视图（不改原 image） ----------
    def combined_image(self):
        """返回 main_image 与 temp_layer 合成后的一张 QImage（用于显示）"""
        out = QImage(self.image)  # copy
        painter = QPainter(out)
        painter.drawImage(0, 0, self.temp)
        painter.end()
        return out

    def update_pixmap(self):
        """把 canvas 和 temp_layer 合成并显示"""
        combined = QImage(self.image)
        painter = QPainter(combined)
        painter.drawImage(0, 0, self.temp)
        painter.end()
        self.setPixmap(QPixmap.fromImage(combined))

    # ---------- 坐标映射 scene -> image ----------
    def scene_to_image(self, scene_x_or_point, maybe_y=None):
        """支持传 QPointF 或 (x,y)"""
        if maybe_y is None:
            # assume scene_x_or_point is QPointF
            sx = scene_x_or_point.x()
            sy = scene_x_or_point.y()
        else:
            sx = scene_x_or_point
            sy = maybe_y

        ix = int(round(sx - self.pos().x()))
        iy = int(round(sy - self.pos().y()))
        return ix, iy

    # ---------- 临时层操作接口 ----------
    def clear_temp(self):
        self.temp.fill(Qt.GlobalColor.transparent)

    # ---------- 将临时层合并到主图 ----------
    def redraw(self):
        # 清空 image
        self.image.fill(self.bg_color)
        # 绘制存储在 self.shapes 的每个 shape（它们应记录 image 坐标和当前 angle）
        for shape in self.shapes:
            if shape.type == 'Line':
                for x0, y0, x1, y1 in shape.get_line():
                    from tool import draw_line_bresenham
                    draw_line_bresenham(self.image, x0, y0, x1, y1, shape.border_color, shape.line_style)
            elif shape.type == 'Polygon':
                self.draw_polygon(shape, "image")
            elif shape.type == 'Ellipse':
                # 此处 draw_ellipse 不会再 append shapes
                self.draw_ellipse(shape, "image")
            elif shape.type == 'Circle':
                from tool import draw_circle_midpoint
                draw_circle_midpoint(self.image, shape.centre, shape.radius, shape.border_color, shape.line_style)
                self._fill_shape(shape, shape.fill_color)
        # 确保 temp 清空（提交到 image 后通常希望清空）
        self.clear_temp()
        self.update_pixmap()


# TODO:将线段作画的参数换为QPointF
    def draw_temp_line(self, x0, y0, x1, y1, color, line_style):
        self.clear_temp()
        # 绘制到 temp
        from tool import draw_line_bresenham
        draw_line_bresenham(self.temp, x0, y0, x1, y1, color, line_style)

        # 更新显示
        self.update_pixmap()

# TODO:像椭圆和多边形一样将圆的temp层和image层整合
    # --------- 在临时层绘制圆 -----------
    def draw_temp_circle(self, centre, r, color, line_style):
        self.clear_temp()
        # 调用工具函数绘制椭圆
        from tool import draw_circle_midpoint
        draw_circle_midpoint(self.temp, centre, r, color, line_style)

        # 刷新显示（不立即清除 temp）
        self.update_pixmap()

    # ---------- 主图绘制 ----------
    def draw_line_to_image(self, x0, y0, x1, y1, color, line_style):
        self.clear_temp()
        self.shapes.append(LineShape(QPointF(x0,y0), QPointF(x1,y1), color, line_style))
        from tool import draw_line_bresenham
        draw_line_bresenham(self.image, x0, y0, x1, y1, color, line_style)
        self.update_pixmap()

    def draw_circle_to_image(self, centre, r, color, line_style):
        self.clear_temp()
        self.shapes.append(CircleShape(centre, r, color, None, line_style))
        from tool import draw_circle_midpoint
        draw_circle_midpoint(self.image, centre, r, color, line_style)
        self.update_pixmap()

    def draw_polygon(self, polygon: PolygonShape, target: str):
        """
        绘制多边形（含填充 + 边界）。
        target: "image" 或 "temp"
        """

        # --- 选择绘制目标 ---
        if target == "temp":
            self.clear_temp()
            target_img = self.temp
        else:
            target_img = self.image

        points = polygon.points
        n = len(points)
        if n < 2:
            return

        W, H = target_img.width(), target_img.height()

        # 1. 填充：扫描线多边形填充
        if polygon.fill_color is not None:
            # 先构建边表（Edge Table）
            edges = []
            for i in range(n):
                p1 = points[i]
                p2 = points[(i + 1) % n]

                x1, y1 = p1.x(), p1.y()
                x2, y2 = p2.x(), p2.y()

                # 跳过水平边
                if y1 == y2:
                    continue

                # 保证 y1 < y2
                if y1 > y2:
                    x1, x2 = x2, x1
                    y1, y2 = y2, y1

                # (ymin, ymax, x_at_ymin, dx/dy)
                edges.append([y1, y2, x1, (x2 - x1) / (y2 - y1)])

            # 扫描线从图像区域内扫描
            for y in range(H):
                # AL (Active List)
                active = []

                for ymin, ymax, x_at_ymin, slope in edges:
                    if ymin <= y < ymax:  # 在有效扫描范围
                        x = x_at_ymin + (y - ymin) * slope
                        active.append(x)

                if not active:
                    continue

                active.sort()

                # 成对填充
                for i in range(0, len(active), 2):
                    x_start = int(active[i])
                    x_end = int(active[i + 1])

                    if x_end < x_start:
                        continue

                    for x in range(x_start, x_end + 1):
                        if 0 <= x < W and 0 <= y < H:
                            target_img.setPixelColor(x, y, polygon.fill_color)

        # 2. 描边：Bresenham 画边
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]

            x1, y1 = int(round(p1.x())), int(round(p1.y()))
            x2, y2 = int(round(p2.x())), int(round(p2.y()))

            draw_line_bresenham(
                target_img,
                x1, y1,
                x2, y2,
                polygon.border_color,
                polygon.line_style
            )
        if target == "temp":
            self.update_pixmap()

    def draw_polygon_points(self, points: list[QPointF], color: QColor):
        """
        绘制多边形边界（可用于临时显示悬浮边）。
        points: 点列表，可以是 PolygonShape.points 或临时加上鼠标点
        target: 'temp' 或 'image'
        color: 边界颜色
        """
        if not points or len(points) < 2:
            return  # 至少需要两点才能画边
        self.clear_temp()
        target_img = self.temp

        W, H = target_img.width(), target_img.height()

        # 遍历每条边绘制（最后一个点到第一个点可以不画，悬浮边时不要闭合）
        for i in range(len(points)-1):
            p1 = points[i]
            p2 = points[i + 1]

            x0, y0 = int(round(p1.x())), int(round(p1.y()))
            x1, y1 = int(round(p2.x())), int(round(p2.y()))

            # 使用 Bresenham 算法绘制直线
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy

            while True:
                if 0 <= x0 < W and 0 <= y0 < H:
                    target_img.setPixelColor(x0, y0, color)

                if x0 == x1 and y0 == y1:
                    break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x0 += sx
                if e2 < dx:
                    err += dx
                    y0 += sy

        self.update_pixmap()

    def draw_ellipse(self, ellipse: EllipseShape, target: str):
        """
        Draw ellipse to either 'temp' or 'image'. 只绘制，不修改 self.shapes。
        """
        self.clear_temp()

        cx, cy = ellipse.centre.x(), ellipse.centre.y()
        a = max(int(ellipse.a), 1)
        b = max(int(ellipse.b), 1)
        angle = ellipse.angle

        target_img = self.image if target == "image" else self.temp
        W, H = target_img.width(), target_img.height()

        if angle == 0.0:
            from tool import draw_ellipse_midpoint
            p1 = QPointF(cx - a, cy - b)
            p2 = QPointF(cx + a, cy + b)
            draw_ellipse_midpoint(target_img, p1, p2, ellipse.border_color, ellipse.line_style)
            if target == "temp":
                self.update_pixmap()
            return

        # 旋转情况：用 parametric/采样法绘制边界（及可选填充）
        import math
        cosA = math.cos(math.radians(angle))
        sinA = math.sin(math.radians(angle))

        # 绘制边界（parametric），steps 与周长成比例
        steps = max(24, int(2 * math.pi * max(a, b)))  # 保守下限防止过小
        dash_len = 6

        # 如果需要填充，先做射线/扫描或保守采样（这里只做边界 + 可选简单内填）
        # 先画 fill（如果有），使用点采样 + 点在旋转椭圆测试
        if ellipse.fill_color is not None:
            # 旋转后的椭圆包围矩形
            dx = (a * a * cosA ** 2 + b * b * sinA ** 2) ** 0.5
            dy = (a * a * sinA ** 2 + b * b * cosA ** 2) ** 0.5

            x_min = max(int(cx - dx), 0)
            x_max = min(int(cx + dx), W - 1)
            y_min = max(int(cy - dy), 0)
            y_max = min(int(cy + dy), H - 1)

            for iy in range(y_min, y_max + 1):
                for ix in range(x_min, x_max + 1):
                    # 相对椭圆中心
                    rx = ix - cx
                    ry = iy - cy
                    # 反旋转到未旋转坐标系
                    x_un = rx * cosA + ry * sinA
                    y_un = -rx * sinA + ry * cosA
                    # 判断是否在椭圆内部
                    if (x_un * x_un) / (a * a) + (y_un * y_un) / (b * b) <= 1.0:
                        target_img.setPixelColor(ix, iy, ellipse.fill_color)

        # 再画边界（parametric），dash 支持
        dash_counter = 0
        for i in range(steps):
            t = 2 * math.pi * i / steps
            x0 = a * math.cos(t)
            y0 = b * math.sin(t)
            # 旋转并平移
            x = cx + x0 * cosA - y0 * sinA
            y = cy + x0 * sinA + y0 * cosA
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < W and 0 <= yi < H:
                if ellipse.line_style == 'solid':
                    target_img.setPixelColor(xi, yi, ellipse.border_color)
                else:
                    # dash pattern: 每 dash_len 像素绘制一段
                    if (dash_counter // dash_len) % 2 == 0:
                        target_img.setPixelColor(xi, yi, ellipse.border_color)
                    dash_counter += 1

        self.update_pixmap()


    # ----------- 扫描线填充算法 --------------
    # State调用fill_at_point来根据用户点击位置进行填充
    def fill_at_point(self, click_point: QPointF, fill_color):
        shape = self.find_shape_at_image_point(click_point)
        self._fill_shape(shape, fill_color)

    # 扫描线填充算法核心
    def _fill_shape(self, shape: VectorShape, fill_color):
        if isinstance(fill_color, Qt.GlobalColor):
            fill_color = QColor(fill_color)

        if fill_color is None:
            return
        if shape.type == "Line":
            print("线段不应当被填充")
            return

        shape.fill_color = fill_color

        # 当前图像偏移
        ox, oy = self.offset_x, self.offset_y

        # 多边形
        if shape.type == 'Polygon':
            edges = shape.get_edges()
            int_edges = []
            for x1, y1, x2, y2 in edges:
                int_edges.append((
                    int(round(x1 + ox)),
                    int(round(y1 + oy)),
                    int(round(x2 + ox)),
                    int(round(y2 + oy))
                ))

            y_min = min(min(y1, y2) for x1, y1, x2, y2 in int_edges)
            y_max = max(max(y1, y2) for x1, y1, x2, y2 in int_edges)

            for y in range(y_min, y_max + 1):
                x_intersections = []
                for x1, y1, x2, y2 in int_edges:
                    if y1 == y2:
                        continue
                    if (y1 <= y < y2) or (y2 <= y < y1):
                        x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                        x_intersections.append(int(round(x)))
                x_intersections.sort()
                for i in range(0, len(x_intersections), 2):
                    if i + 1 < len(x_intersections):
                        x_start = x_intersections[i]
                        x_end = x_intersections[i + 1]
                        for x in range(x_start + 1, x_end):
                            if 0 <= x < self.image.width() and 0 <= y < self.image.height():
                                self.image.setPixelColor(x, y, fill_color)

        # 圆 / 椭圆
        elif shape.type in ('Circle', 'Ellipse'):
            cx = shape.centre.x() + ox
            cy = shape.centre.y() + oy

            if shape.type == 'Circle':
                r = shape.radius
                r2 = r * r

                for y in range(int(cy - r), int(cy + r) + 1):

                    dy = y - cy
                    d2 = r2 - dy * dy
                    if d2 < 0:
                        continue  # 浮点误差保护

                    # 加 1e-9 避免 sqrt 结果变成 14.99999999 这种
                    dx_limit = int((d2 ** 0.5) + 1e-9)

                    # 这里要包含端点，否则必然留一条白缝
                    x_start = int(cx - dx_limit)
                    x_end = int(cx + dx_limit)

                    for x in range(x_start, x_end + 1):
                        if 0 <= x < self.image.width() and 0 <= y < self.image.height():
                            self.image.setPixelColor(x, y, fill_color)
            elif shape.type == 'Ellipse':
                from math import cos, sin, radians
                cx = shape.centre.x() + ox
                cy = shape.centre.y() + oy
                a, b = shape.a, shape.b
                a2, b2 = a * a, b * b
                angle = getattr(shape, 'angle', 0.0)  # 旋转角度，度
                cosA = cos(radians(-angle))  # 反旋转
                sinA = sin(radians(-angle))
                H, W = self.image.height(), self.image.width()

                # 旋转椭圆的包围矩形
                dx = (a2 * cosA ** 2 + b2 * sinA ** 2) ** 0.5
                dy = (a2 * sinA ** 2 + b2 * cosA ** 2) ** 0.5

                x_min = max(int(cx - dx), 0)
                x_max = min(int(cx + dx), W - 1)
                y_min = max(int(cy - dy), 0)
                y_max = min(int(cy + dy), H - 1)

                for iy in range(y_min, y_max + 1):
                    for ix in range(x_min, x_max + 1):
                        # 相对椭圆中心
                        x_rel = ix - cx
                        y_rel = iy - cy
                        # 反旋转到未旋转坐标系
                        x_un = x_rel * cosA - y_rel * sinA
                        y_un = x_rel * sinA + y_rel * cosA
                        # 判断椭圆内部
                        if (x_un * x_un) / a2 + (y_un * y_un) / b2 <= 1.0:
                            self.image.setPixelColor(ix, iy, fill_color)

        self.update_pixmap()

    # ---------- 旋转 ------------
    def rotate(self, delta_angle: float, shape: VectorShape):
        self._rotate_shape(delta_angle, shape)

    def _rotate_shape(self, delta_angle: float, shape: VectorShape):
        shape.rotate(delta_angle)
        self._draw_shape_to_temp(shape)

    #------- 拖放 --------
    def drag_and_drop(self, dx, dy, shape: VectorShape):
        self._drag_and_drop_shape(dx, dy, shape)

    def _drag_and_drop_shape(self, dx, dy, shape: VectorShape):
        shape.drag_and_drop(dx, dy)
        self._draw_shape_to_temp(shape)

    # ---------- 选择与变换工具 ----------
    def find_shape_at_image_point(self, point):
        # Scene 坐标 -> Image 坐标
        ix, iy = self.scene_to_image(point)
        point_in_image = QPointF(ix, iy)

        for shape in reversed(self.shapes):
            if shape.contains(point_in_image):
                return shape

    def _draw_shape_to_temp(self, shape: VectorShape):
        # 根据 shape 类型绘制到 temp 层
        if shape.type == 'Line':
            for x0, y0, x1, y1 in shape.get_line():
                self.draw_temp_line(x0, y0, x1, y1, shape.border_color, shape.line_style)

        elif shape.type == 'Polygon':
            self.draw_polygon(shape, 'temp')

        elif shape.type == 'Ellipse':
            # 旋转后的椭圆暂时用中心点 + a,b + angle绘制
            self.draw_ellipse(shape, 'temp')

        elif shape.type == 'Circle':
            # 旋转对圆无影响
            self.draw_temp_circle(shape.centre, shape.radius, shape.border_color, shape.line_style)

        # 刷新显示
        self.update_pixmap()

    def save(self, path: str):
        """
        保存画布内容（包括 temp 层）到文件
        """
        if not hasattr(self, 'image'):
            print("没有 image 属性，无法保存")
            return False

        # 合并 image 和 temp
        combined = self.image.copy()
        painter = QPainter(combined)
        if hasattr(self, 'temp'):
            painter.drawImage(0, 0, self.temp)
        painter.end()

        # 自动添加后缀
        if not path.lower().endswith((".png", ".jpg", ".jpeg")):
            path += ".png"

        success = combined.save(path)
        if not success:
            print(f"保存失败: {path}")
        return success



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