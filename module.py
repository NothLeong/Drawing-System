from PySide6.QtWidgets import QGraphicsView, QTextEdit, QGraphicsPixmapItem
from PySide6.QtGui import QWheelEvent, QImage, QPixmap, QPainter, QColor
from PySide6 import QtCore
from PySide6.QtCore import Qt, QPointF
import re
from VectorShape import *
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
        # 平滑缩放
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)

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

class RasterCanvas(QGraphicsPixmapItem):
    """像素画布 + 临时层（预览），支持自动扩展 & 合并显示"""

    def __init__(self, width=800, height=600, bg_color=Qt.white):
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

    def ensure_contains(self, *points: QPointF):
        """
        确保 image 和 temp 层包含给定的所有 QPointF。
        返回 (x_offset, y_offset) —— 旧图在新图中的偏移（用于重算坐标）。
        """
        if not points:
            return 0, 0

        xs = [int(round(p.x())) for p in points]
        ys = [int(round(p.y())) for p in points]

        ix_min, iy_min = min(xs), min(ys)
        ix_max, iy_max = max(xs), max(ys)

        # 检查是否完全在当前 image 范围内
        if 0 <= ix_min < self.image.width() and 0 <= iy_min < self.image.height() and \
                0 <= ix_max < self.image.width() and 0 <= iy_max < self.image.height():
            return 0, 0

        # 需要扩容
        left = min(0, ix_min)
        top = min(0, iy_min)
        right = max(self.image.width() - 1, ix_max)
        bottom = max(self.image.height() - 1, iy_max)

        new_w = right - left + 1
        new_h = bottom - top + 1
        x_off = -left
        y_off = -top

        # 新 image & temp
        new_img = QImage(new_w, new_h, QImage.Format.Format_ARGB32)
        new_img.fill(self.bg_color)
        new_temp = QImage(new_w, new_h, QImage.Format.Format_ARGB32)
        new_temp.fill(Qt.transparent)

        # 复制旧图
        p = QPainter(new_img)
        p.drawImage(x_off, y_off, self.image)
        p.end()
        p = QPainter(new_temp)
        p.drawImage(x_off, y_off, self.temp)
        p.end()

        # 更新
        self.image = new_img
        self.temp = new_temp
        self.offset_x += x_off
        self.offset_y += y_off

        # 更新 pixmap 和 scene 位置
        self.setPixmap(QPixmap.fromImage(self.combined_image()))
        self.setPos(left, top)
        return x_off, y_off

    # ---------- 临时层操作接口 ----------
    def clear_temp(self):
        self.temp.fill(Qt.GlobalColor.transparent)

    # ---------- 将临时层合并到主图 ----------
    def commit_temp_to_image(self):
        painter = QPainter(self.image)
        painter.drawImage(0, 0, self.temp)
        painter.end()
        # 清空 temp 并刷新显示
        self.clear_temp()
        self.update_pixmap()

    def draw_temp_line(self, x0, y0, x1, y1, color):
        # 一次性确保两个端点都在范围内
        ox, oy = self.ensure_contains(QPointF(x0, y0), QPointF(x1, y1))
        nx0 = x0 + ox
        ny0 = y0 + oy
        nx1 = x1 + ox
        ny1 = y1 + oy

        # 绘制到 temp
        from tool import draw_line_bresenham
        draw_line_bresenham(self.temp, nx0, ny0, nx1, ny1, color)

        # 更新显示
        self.update_pixmap()

    # --------- 在临时层绘制椭圆 -----------
    def draw_temp_ellipse(self, p1, p2, color):
        # 提取坐标
        x0, y0 = p1.x(), p1.y()
        x1, y1 = p2.x(), p2.y()

        # 确保端点在范围内，并计算偏移
        ox, oy = self.ensure_contains(p1, p2)
        nx0 = x0 + ox
        ny0 = y0 + oy
        nx1 = x1 + ox
        ny1 = y1 + oy

        # 调用工具函数绘制椭圆
        from tool import draw_ellipse_midpoint
        draw_ellipse_midpoint(self.temp, QPointF(nx0, ny0), QPointF(nx1, ny1), color)

        # 刷新显示（不立即清除 temp）
        self.update_pixmap()

    # --------- 在临时层绘制圆 -----------
    def draw_temp_circle(self, centre, r, color):
        xc, yc = centre.x(), centre.y()
        ox, oy = self.ensure_contains(centre)

        nxc, nyc = xc + ox, yc + oy

        # 调用工具函数绘制椭圆
        from tool import draw_circle_midpoint
        draw_circle_midpoint(self.temp, QPointF(nxc, nyc), r, color)

        # 刷新显示（不立即清除 temp）
        self.update_pixmap()

    # ---------- 直接在主图绘制（用于最终 commit） ----------
    def draw_line_to_image(self, x0, y0, x1, y1, color):
        ox, oy = self.ensure_contains(QPointF(x0, y0), QPointF(x1, y1))
        nx0 = x0 + ox
        ny0 = y0 + oy
        nx1 = x1 + ox
        ny1 = y1 + oy

        self.shapes.append(LineShape(QPointF(x0,y0), QPointF(x1,y1), color))
        from tool import draw_line_bresenham
        draw_line_bresenham(self.image, nx0, ny0, nx1, ny1, color)
        self.update_pixmap()

    # ---------- 直接在主图绘制（用于最终 commit） ----------
    def draw_circle_to_image(self, centre, r, color):
        xc, yc = centre.x(), centre.y()
        ox, oy = self.ensure_contains(centre)

        nxc, nyc = xc+ox, yc+oy
        nc = QPointF(nxc,nyc)
        self.shapes.append(CircleShape(centre, r, color, None))
        from tool import draw_circle_midpoint
        draw_circle_midpoint(self.image, nc, r, color)
        self.update_pixmap()

    # --------- 在主图绘制椭圆 -----------
    def draw_ellipse_to_image(self, p1, p2, color):
        x0, y0 = p1.x(), p1.y()
        x1, y1 = p2.x(), p2.y()

        # 确保端点在范围内，并计算偏移
        ox, oy = self.ensure_contains(p1, p2)
        nx0, ny0 = x0 + ox, y0 + oy
        nx1, ny1 = x1 + ox, y1 + oy
        np1 = QPointF(nx0,ny0)
        np2 = QPointF(nx1,ny1)
        self.shapes.append(EllipseShape(p1, p2, color, None))
        from tool import draw_ellipse_midpoint
        draw_ellipse_midpoint(self.image, np1, np2, color)
        self.update_pixmap()


    # ----------- 扫描线填充算法 --------------
    # State调用fill_at_point来根据用户点击位置进行填充
    def fill_at_point(self, click_point: QPointF, fill_color):
        # Scene 坐标 -> Image 坐标
        ix, iy = self.scene_to_image(click_point)
        click_in_image = QPointF(ix, iy)

        print("执行向量图搜索")
        for shape in reversed(self.shapes):
            if shape.contains(click_in_image):
                self._fill_shape(shape, fill_color)
                print(f"{shape.type}")
                break

    # 扫描线填充算法核心
    def _fill_shape(self, shape: VectorShape, fill_color):
        if isinstance(fill_color, Qt.GlobalColor):
            fill_color = QColor(fill_color)

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
                cx = shape.centre.x() + ox
                cy = shape.centre.y() + oy

                a, b = shape.a, shape.b
                a2, b2 = a * a, b * b
                H, W = self.image.height(), self.image.width()

                # 扫描 y
                for iy in range(int(cy - b), int(cy + b) + 1):
                    if iy < 0 or iy >= H:
                        continue

                    dy = iy - cy

                    # 类似圆: part = a²b² - a²*dy²
                    part = a2 * b2 - a2 * dy * dy
                    if part < 0:
                        continue  # 浮点保护

                    dx = (part / b2) ** 0.5

                    x_start = int(cx - dx + 1e-9)
                    x_end = int(cx + dx + 1e-9)

                    # 填充线段
                    for ix in range(x_start, x_end + 1):
                        if 0 <= ix < W:
                            self.image.setPixelColor(ix, iy, fill_color)

        self.update_pixmap()


    # ---------- 选择与变换工具 ----------
    def find_shape_at_image_point(self, ix, iy):
        """返回最顶层（最后 append）的 shape 或 None； ix,iy 是 image 坐标"""
        p = QPointF(ix, iy)
        for shape in reversed(self.shapes):
            # 只有填充/边界某些形可被选中，可根据需求也允许选择边线
            try:
                if shape.contains(p):
                    return shape
            except Exception:
                continue
        return None

    def translate_shape(self, shape: VectorShape, dx, dy):
        """把 shape 在 image 坐标系中移动（立即生效到 image 或 temp，取决场景）"""
        shape.translate(dx, dy)
        # 立即重绘受影响区域：简单起见，重画全部（或优化为局部）
        self.redraw_all_shapes()

    def rotate_shape(self, shape: VectorShape, angle_deg, center=None):
        shape.rotate(angle_deg, center)
        self.redraw_all_shapes()

    def redraw_all_shapes(self):
        """使用 shapes 的矢量信息重绘 self.image（保持 offset 不变）"""
        # 清空 image（保留 bg）
        w,h = self.image.width(), self.image.height()
        self.image.fill(self.bg_color)
        # 逐个绘制 shape 的边界与填充（注意：绘制边界时使用边界像素方法）
        from tool import draw_line_bresenham, draw_circle_midpoint, draw_ellipse_midpoint
        for shape in self.shapes:
            if shape.type == 'Line':
                (x1,y1,x2,y2) = shape.get_line()[0]
                # 用偏移量 ox/oy already included in shapes if shapes store image coords,
                # else add self.offset_x/self.offset_y
                draw_line_bresenham(self.image, int(x1), int(y1), int(x2), int(y2), shape.border_color)
            elif shape.type == 'Circle':
                cx = int(round(shape.centre.x()))
                cy = int(round(shape.centre.y()))
                draw_circle_midpoint(self.image, QPointF(cx,cy), shape.radius, shape.border_color)
            elif shape.type == 'Ellipse':
                p1 = QPointF(shape.centre.x()-shape.a, shape.centre.y()-shape.b)
                p2 = QPointF(shape.centre.x()+shape.a, shape.centre.y()+shape.b)
                draw_ellipse_midpoint(self.image, p1, p2, shape.border_color)
            elif shape.type == 'Polygon':
                # draw polygon edges
                edges = shape.get_edges()
                for x1,y1,x2,y2 in edges:
                    draw_line_bresenham(self.image, int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)), shape.border_color)
            # 填充如果 shape.fill_color 非空可以执行你已有 _fill_shape 的填充逻辑（或延后）
        # 刷新显示
        self.update_pixmap()


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