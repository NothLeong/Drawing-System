from PySide6.QtWidgets import QGraphicsView, QTextEdit, QGraphicsPixmapItem
from PySide6.QtGui import QWheelEvent, QImage, QPixmap, QPainter, QColor, QVector3D
from PySide6 import QtCore
from PySide6.QtCore import Qt, QPointF
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

        self.show_curve_skeletons = False  # 用来显示所有曲线的控制多边形

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
            elif shape.type == 'Curve':
                self.draw_curve(shape, 'image')
        # 确保 temp 清空（提交到 image 后通常希望清空）
        self.clear_temp()

        if self.show_curve_skeletons:
            for shape in self.shapes:
                if shape.type == 'Curve':
                    self.draw_curve_skeleton(shape)

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

    def draw_curve(self, curve_shape, target: str):
        from tool import (de_casteljau, calculate_b_spline_point, generate_clamped_knots)

        target_img = self.image if target == "image" else self.temp
        pts = curve_shape.control_points
        n = len(pts)
        if n < 2: return

        sampled_points = []
        precision = curve_shape.precision

        # --- 1. 计算采样点 (保持原有逻辑不变) ---
        if curve_shape.curve_type == "Bezier":
            for i in range(precision + 1):
                sampled_points.append(de_casteljau(pts, i / precision))

        elif curve_shape.curve_type == "B-Spline":
            k = min(4, n)
            knots = generate_clamped_knots(n, k)
            max_t = knots[-1]
            for i in range(precision + 1):
                t = (i / precision) * max_t
                if t >= max_t: t = max_t - 0.0001
                sampled_points.append(calculate_b_spline_point(pts, t, k, knots))

        # --- 2. 光栅化：连接采样点  ---
        # 不能直接调用 draw_line_bresenham，因为每一小段都会重置虚线计数器。
        # 这里需要手动实现 Bresenham，并维护一个全局的 step_counter。

        W, H = target_img.width(), target_img.height()
        color = curve_shape.border_color
        style = curve_shape.line_style

        # 虚线参数
        dash_len = 5  # 实线/空白的长度（像素）
        step_counter = 0  # 全局步长计数器，用于计算虚线周期

        for i in range(len(sampled_points) - 1):
            p1 = sampled_points[i]
            p2 = sampled_points[i + 1]

            x0, y0 = int(round(p1.x())), int(round(p1.y()))
            x1, y1 = int(round(p2.x())), int(round(p2.y()))

            # --- 内联 Bresenham 算法 ---
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy

            while True:
                # 判断当前像素是否需要绘制
                should_draw = True
                if style == 'dash':
                    # 按照 dash_len 进行取模判断：画一段，空一段
                    # (step_counter // dash_len) % 2 == 0 表示画实线
                    # (step_counter // dash_len) % 2 == 1 表示空白
                    if (step_counter // dash_len) % 2 != 0:
                        should_draw = False

                if should_draw:
                    if 0 <= x0 < W and 0 <= y0 < H:
                        target_img.setPixelColor(x0, y0, color)

                # 无论画不画，计数器都要增加，保持纹理连续
                step_counter += 1

                # 到达终点，跳出当前线段循环，进入下一段采样
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

    def draw_curve_skeleton(self, curve_shape):
        """在 temp 层绘制曲线的控制多边形和顶点"""
        pts = curve_shape.control_points
        if not pts: return

        # 1. 绘制虚线连线 (控制多边形)
        c_line = QColor(Qt.GlobalColor.blue)
        c_line.setAlpha(150)

        # 转换点坐标到整数以便 Bresenham 使用
        int_pts = []
        for p in pts:
            int_pts.append((int(round(p.x())), int(round(p.y()))))

        if len(int_pts) > 1:
            for i in range(len(int_pts) - 1):
                draw_line_bresenham(self.temp,
                                    int_pts[i][0], int_pts[i][1],
                                    int_pts[i + 1][0], int_pts[i + 1][1],
                                    c_line, 'dash')
            # 如果是闭合曲线或者为了显示方便，也可以连首尾，这里对于B样条通常不连首尾除非闭合

        # 2. 绘制控制点 (小圆圈)
        c_point = QColor(Qt.GlobalColor.red)
        r = 4  # 顶点半径
        for ix, iy in int_pts:
            # 简单绘制一个小实心方块或者圆
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:  # 圆
                        nx, ny = ix + dx, iy + dy
                        if 0 <= nx < self.temp.width() and 0 <= ny < self.temp.height():
                            self.temp.setPixelColor(nx, ny, c_point)
        self.update_pixmap()

    def fill_surface_mesh(self, img, mesh, surface):
        """将曲面切分为微小三角形并使用重心坐标填充渐变色"""
        for i in range(surface.u_segments):
            for j in range(surface.v_segments):
                # 定义矩形格子的四个顶点
                p1, p2 = mesh[i][j], mesh[i + 1][j]
                p3, p4 = mesh[i + 1][j + 1], mesh[i][j + 1]

                # 计算顶点颜色（这里简化：基于u,v在控制网格颜色间线性插值）
                # 实际上应该用双线性插值获取四个角的颜色 c1,c2,c3,c4
                c1 = QColor(255, (i * 10) % 255, (j * 10) % 255)  # 示例渐变色
                c2 = QColor(100, (i * 10) % 255, (j * 10) % 255)

                # 拆分为两个三角形进行填充
                self.fill_triangle_gradient(img, p1, p2, p3, c1, c2, c1)
                self.fill_triangle_gradient(img, p1, p3, p4, c1, c1, c2)


    # ----------- 扫描线填充算法 --------------
    # State调用fill_at_point来根据用户点击位置进行填充
    def fill_at_point(self, click_point: QPointF, fill_color):
        shape = self.find_shape_at_image_point(click_point)
        self._fill_shape(shape, fill_color)

    def find_control_point(self, pos: QPointF, threshold=8.0):
        """
        遍历所有曲线，寻找距离 pos 最近的控制点
        返回: (curve_shape, point_index) 或 None
        """
        for shape in reversed(self.shapes): # 从后往前找，优先选中上层
            if shape.type == 'Curve':
                for i, p in enumerate(shape.control_points):
                    # 计算距离
                    dx = p.x() - pos.x()
                    dy = p.y() - pos.y()
                    if (dx*dx + dy*dy) <= threshold**2:
                        return shape, i
        return None

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
        elif shape.type == 'Curve':
            self.draw_curve(shape, 'temp')

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


import sys
from PySide6.QtWidgets import (QApplication, QMainWindow,
                               QWidget, QVBoxLayout, QHBoxLayout, QSlider,
                               QLabel, QGroupBox, QComboBox, QRadioButton,
                               QButtonGroup)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QVector3D, QSurfaceFormat

# OpenGL 库
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from tool import de_casteljau_3d

import colorsys


# ---------------------------
# OpenGL 渲染 Widget
# ---------------------------
class GLSurfaceWidget(QOpenGLWidget):
    point_selected = Signal(int, int)
    point_dragged = Signal(int, int, QVector3D)

    def __init__(self, grid_size):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)

        self.rot_x = 30.0;
        self.rot_y = 45.0;
        self.zoom = -30.0
        self.pan_x = 0.0;
        self.pan_y = 0.0
        self.last_pos = None
        self.is_dragging_point = False
        self.drag_win_z = 0.0
        self.render_mode = 1

        # 网格生成
        self.grid_size = grid_size
        self.control_grid = []
        span = 12.0
        step = span / (self.grid_size - 1)
        start = -span / 2.0

        import math
        for r in range(self.grid_size):
            row_data = []
            z = start + r * step
            for c in range(self.grid_size):
                x = start + c * step
                dist = (x ** 2 + z ** 2) ** 0.5
                y = 5.0 * math.cos(dist * 0.3)
                row_data.append(QVector3D(x, y, z))
            self.control_grid.append(row_data)

        # 越大，效果越好，但越卡
        self.res = 20

        self.surface_data = []
        self.selected_idx = (1, 1)
        self.init_surface_data()

    # --- 交互逻辑 ---
    def get_event_pos(self, e):
        return e.position().toPoint() if hasattr(e, 'position') else e.pos()

    def mousePressEvent(self, e):
        self.last_pos = self.get_event_pos(e)
        if e.button() == Qt.LeftButton:
            hit, z = self.pick_point(self.last_pos.x(), self.last_pos.y())
            if hit:
                self.is_dragging_point = True; self.drag_win_z = z
            else:
                self.is_dragging_point = False

    def mouseMoveEvent(self, e):
        curr = self.get_event_pos(e)
        if not self.last_pos: self.last_pos = curr; return
        dx, dy = curr.x() - self.last_pos.x(), curr.y() - self.last_pos.y()
        if self.is_dragging_point and (e.buttons() & Qt.LeftButton):
            self.move_selected_point(curr.x(), curr.y())
        elif e.buttons() & Qt.LeftButton:
            self.pan_x += dx * 0.05; self.pan_y -= dy * 0.05
        elif e.buttons() & Qt.RightButton:
            self.rot_x += dy * 0.5; self.rot_y += dx * 0.5
        self.last_pos = curr;
        self.update()

    def mouseReleaseEvent(self, e):
        self.is_dragging_point = False

    def wheelEvent(self, e):
        self.zoom += e.angleDelta().y() / 120; self.update()

    def set_transform(self):
        glTranslatef(0, 0, self.zoom);
        glTranslatef(self.pan_x, self.pan_y, 0)
        glRotatef(self.rot_x, 1, 0, 0);
        glRotatef(self.rot_y, 0, 1, 0);
        glTranslatef(0, -2, 0)

    def move_selected_point(self, mx, my):
        self.makeCurrent();
        glLoadIdentity();
        self.set_transform()
        mv = glGetDoublev(GL_MODELVIEW_MATRIX);
        proj = glGetDoublev(GL_PROJECTION_MATRIX);
        vp = glGetIntegerv(GL_VIEWPORT)
        r = self.devicePixelRatio();
        wy = vp[3] - (my * r)
        try:
            wx, wy, wz = gluUnProject(mx * r, wy, self.drag_win_z, mv, proj, vp)
            ri, ci = self.selected_idx
            self.control_grid[ri][ci] = QVector3D(wx, wy, wz)
            self.refresh_surface();
            self.point_dragged.emit(ri, ci, QVector3D(wx, wy, wz))
        except:
            pass

    def pick_point(self, mx, my):
        self.makeCurrent();
        glLoadIdentity();
        self.set_transform()
        mv = glGetDoublev(GL_MODELVIEW_MATRIX);
        proj = glGetDoublev(GL_PROJECTION_MATRIX);
        vp = glGetIntegerv(GL_VIEWPORT)
        r = self.devicePixelRatio();
        px, py = mx * r, my * r
        min_d = 30.0 * r;
        idx = None;
        fz = 0.0
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                p = self.control_grid[i][j]
                try:
                    wx, wy, wz = gluProject(p.x(), p.y(), p.z(), mv, proj, vp)
                    d = ((wx - px) ** 2 + ((vp[3] - wy) - py) ** 2) ** 0.5
                    if d < min_d: min_d = d; idx = (i, j); fz = wz
                except:
                    continue
        if idx: self.selected_idx = idx; self.point_selected.emit(*idx); self.update(); return True, fz
        return False, 0.0

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST);
        glEnable(GL_BLEND);
        glShadeModel(GL_SMOOTH)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.15, 0.15, 0.15, 1.0)
        self.init_surface_data()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h);
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity()
        gluPerspective(45, w / max(h, 1), 0.1, 200);
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        glLoadIdentity()
        self.set_transform()
        self.draw_reference_grid()
        self.draw_surface()
        self.draw_control_cage()

    def get_color_by_height(self, y):
        if y <= 0:
            t = max(0.0, min(1.0, (y * 5 + 10) / 10)); h = 0.7 * (1 - t) + 0.5 * t
        else:
            t = max(0.0, min(1.0, y * 5 / 10)); h = 0.5 * (1 - t)
        return colorsys.hsv_to_rgb(h, 1.0, 1.0)

    # -------------------------------------------------------------
    #  核心：扫描线算法
    # -------------------------------------------------------------
    def draw_scanline_triangle(self, v1, v2, v3, c1, c2, c3):
        # 1. 排序 Y (High -> Low)
        pts = [(v1, c1), (v2, c2), (v3, c3)]
        pts.sort(key=lambda p: p[0][1], reverse=True)
        (p1, col1), (p2, col2), (p3, col3) = pts

        y1, y2, y3 = int(p1[1]), int(p2[1]), int(p3[1])
        if y1 == y3: return

        def interpolate(y, ya, yb, va, vb):
            if ya == yb: return va
            t = (y - ya) / (yb - ya)
            if isinstance(va, tuple):
                return tuple(va[i] + t * (vb[i] - va[i]) for i in range(3))
            return va + t * (vb - va)

        # 扫描行
        for y in range(y1, y3 - 1, -1):
            # 长边插值
            xl = interpolate(y, y1, y3, p1[0], p3[0])
            zl = interpolate(y, y1, y3, p1[2], p3[2])
            cl = interpolate(y, y1, y3, col1, col3)

            # 短边插值
            if y > y2:  # 上半段
                xr = interpolate(y, y1, y2, p1[0], p2[0])
                zr = interpolate(y, y1, y2, p1[2], p2[2])
                cr = interpolate(y, y1, y2, col1, col2)
            else:  # 下半段
                xr = interpolate(y, y2, y3, p2[0], p3[0])
                zr = interpolate(y, y2, y3, p2[2], p3[2])
                cr = interpolate(y, y2, y3, col2, col3)

            if xl > xr:
                xl, xr = xr, xl
                zl, zr = zr, zl
                cl, cr = cr, cl

            start_x, end_x = int(xl), int(xr)
            if start_x == end_x: continue

            # 横向逐像素绘制
            for x in range(start_x, end_x):
                # 像素级插值
                z = interpolate(x, start_x, end_x, zl, zr)
                c = interpolate(x, start_x, end_x, cl, cr)

                glColor3f(*c)
                glVertex3f(x, y, z)

    def draw_surface(self):
        if self.render_mode == 1:
            # === 模式 1: 纯手动光栅化 (画点) ===
            mv = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj = glGetDoublev(GL_PROJECTION_MATRIX)
            vp = glGetIntegerv(GL_VIEWPORT)

            # 压栈保护
            glMatrixMode(GL_PROJECTION);
            glPushMatrix();
            glLoadIdentity()
            glOrtho(0, vp[2], 0, vp[3], -200, 200)  # Z范围很大防止裁剪
            glMatrixMode(GL_MODELVIEW);
            glPushMatrix();
            glLoadIdentity()

            try:
                glPointSize(1.5)  # 点大一点，填补缝隙
                glBegin(GL_POINTS)

                for i in range(self.res):
                    for j in range(self.res):
                        q = [self.surface_data[i][j], self.surface_data[i + 1][j],
                             self.surface_data[i + 1][j + 1], self.surface_data[i][j + 1]]

                        s_pts = [];
                        cols = []
                        for p in q:
                            wx, wy, wz = gluProject(p.x(), p.y(), p.z(), mv, proj, vp)
                            s_pts.append((wx, wy, wz))
                            cols.append(self.get_color_by_height(p.y()))

                        self.draw_scanline_triangle(s_pts[0], s_pts[1], s_pts[2], cols[0], cols[1], cols[2])
                        self.draw_scanline_triangle(s_pts[0], s_pts[2], s_pts[3], cols[0], cols[2], cols[3])

                glEnd()
            except Exception as e:
                print(f"Render Error: {e}")
                try:
                    glEnd()
                except:
                    pass
            finally:
                glMatrixMode(GL_PROJECTION);
                glPopMatrix()
                glMatrixMode(GL_MODELVIEW);
                glPopMatrix()

        else:
            # === 模式 0: 线框 ===
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);
            glLineWidth(1.0);
            glColor3f(0, 1, 1)
            try:
                for i in range(self.res):
                    glBegin(GL_TRIANGLE_STRIP)
                    for j in range(self.res + 1):
                        p1 = self.surface_data[i][j];
                        p2 = self.surface_data[i + 1][j]
                        glVertex3f(p1.x(), p1.y(), p1.z());
                        glVertex3f(p2.x(), p2.y(), p2.z())
                    glEnd()
            except:
                glEnd()
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def draw_reference_grid(self):
        glLineWidth(1.0);
        glColor4f(0.4, 0.4, 0.4, 0.5);
        glBegin(GL_LINES);
        s = 12
        for i in range(-s, s + 1, 2):
            glVertex3f(i, -0.1, -s);
            glVertex3f(i, -0.1, s);
            glVertex3f(-s, -0.1, i);
            glVertex3f(s, -0.1, i)
        glEnd()

    def draw_control_cage(self):
        glDisable(GL_DEPTH_TEST);
        glLineWidth(1.0);
        glColor3f(1, 1, 0.4);
        glBegin(GL_LINES)
        for r in range(self.grid_size):
            for c in range(self.grid_size - 1):
                p1 = self.control_grid[r][c];
                p2 = self.control_grid[r][c + 1]
                glVertex3f(p1.x(), p1.y(), p1.z());
                glVertex3f(p2.x(), p2.y(), p2.z())
        for c in range(self.grid_size):
            for r in range(self.grid_size - 1):
                p1 = self.control_grid[r][c];
                p2 = self.control_grid[r + 1][c]
                glVertex3f(p1.x(), p1.y(), p1.z());
                glVertex3f(p2.x(), p2.y(), p2.z())
        glEnd()
        glPointSize(8.0);
        glBegin(GL_POINTS)
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                p = self.control_grid[r][c]
                if (r, c) == self.selected_idx:
                    glColor3f(1, 0.2, 0.2)
                else:
                    glColor3f(0.4, 1.0, 0.4)
                glVertex3f(p.x(), p.y(), p.z())
        glEnd();
        glEnable(GL_DEPTH_TEST)

    def update_control_point(self, r, c, pos):
        self.control_grid[r][c] = pos; self.refresh_surface()

    def set_selected_index(self, r, c):
        self.selected_idx = (r, c); self.update()

    def refresh_surface(self):
        self.init_surface_data(); self.update()

    def set_render_mode(self, mode):
        self.render_mode = mode; self.update()

    def init_surface_data(self):
        self.surface_data = []
        for i in range(self.res + 1):
            u = i / self.res;
            row = []
            for j in range(self.res + 1):
                v = j / self.res;
                v_ctrl = []
                for c in range(self.grid_size):
                    col = [self.control_grid[r][c] for r in range(self.grid_size)]
                    v_ctrl.append(de_casteljau_3d(col, u))
                row.append(de_casteljau_3d(v_ctrl, v))
            self.surface_data.append(row)


# ---------------------------
# 主窗口
# ---------------------------
class SurfaceEditorWindow(QMainWindow):
    def __init__(self, parent=None):
        # ---------------------------------------------------------
        # 兼容性处理：
        # QMainWindow 的 super().__init__ 只能接收 QWidget 类型或 None。
        # ---------------------------------------------------------
        qt_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(qt_parent)

        # 保存 state 引用 (如果你将来需要调用 State 类里的方法)
        self.state = parent
        # 双三次bezier曲面需要16个顶点，现在的项目结构可以简单升级到更高次,但更高次会导致卡顿
        self.grid_size = self.state.grid_size

        self.setWindowTitle("3D Bicubic Bezier Surface Editor")
        self.resize(1100, 750)
        self.setWindowTitle("3D Bicubic Bezier Surface Editor")
        self.resize(1100, 750)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        self.gl_widget = GLSurfaceWidget(self.grid_size)
        self.gl_widget.point_selected.connect(self.on_gl_point_selected)
        self.gl_widget.point_dragged.connect(self.on_gl_point_dragged)

        layout.addWidget(self.gl_widget, stretch=3)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        layout.addWidget(panel, stretch=1)

        gb_mode = QGroupBox("可视化模式")
        vbox_mode = QVBoxLayout(gb_mode)
        self.rb_wire = QRadioButton("网格线")
        self.rb_fill = QRadioButton("热力图填充");
        self.rb_fill.setChecked(True)
        self.bg_mode = QButtonGroup()
        self.bg_mode.addButton(self.rb_wire, 0);
        self.bg_mode.addButton(self.rb_fill, 1)
        self.bg_mode.idToggled.connect(self.on_mode_changed)
        vbox_mode.addWidget(self.rb_wire);
        vbox_mode.addWidget(self.rb_fill)
        panel_layout.addWidget(gb_mode)

        gb_sel = QGroupBox(f"控制点选择 ({self.grid_size}x{self.grid_size})")
        vbox_sel = QVBoxLayout(gb_sel)
        self.combo_pts = QComboBox()
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                self.combo_pts.addItem(f"Point [{r}, {c}]", (r, c))
        self.combo_pts.setCurrentIndex(5)  # 默认选中 (1,1)
        self.combo_pts.currentIndexChanged.connect(self.on_pt_changed)
        vbox_sel.addWidget(self.combo_pts)
        panel_layout.addWidget(gb_sel)

        gb_coord = QGroupBox("坐标修改")
        vbox_coord = QVBoxLayout(gb_coord)
        self.sliders = {}
        for axis in ['X', 'Y', 'Z']:
            h = QHBoxLayout();
            h.addWidget(QLabel(axis))
            s = QSlider(Qt.Horizontal);
            s.setRange(-100, 100)
            s.valueChanged.connect(self.on_slider_changed)
            h.addWidget(s);
            self.sliders[axis] = s;
            vbox_coord.addLayout(h)
        panel_layout.addWidget(gb_coord)

        # -------- 操作说明 -------
        gb_hint = QGroupBox("操作说明")
        vbox_hint = QVBoxLayout(gb_hint)

        # 使用 HTML 格式增强显示效果
        hint_text = (
            "<b>鼠标操作：</b><br>"
            "• 左键拖动：平移视角 / 拖拽控制点<br>"
            "• 右键拖动：旋转视角<br>"
            "• 滚轮滚动：缩放视图<br>"
            "<br>"
            "<b>提示：</b><br>"
            "直接点击画面中的圆点可选中并修改形状。"
            "由于这里手动实现扫描线算法，没法使用GPU加速，所以在热力图模式下改变曲面、调整视图会很慢。建议在网格模式下操作后再切换回热力图观看效果"
        )

        lbl_hint = QLabel(hint_text)
        lbl_hint.setTextFormat(Qt.RichText)  # 启用 HTML
        lbl_hint.setStyleSheet("QLabel { color: #555555; font-size: 12px; }")
        lbl_hint.setWordWrap(True)  # 允许自动换行

        vbox_hint.addWidget(lbl_hint)
        panel_layout.addWidget(gb_hint)

        panel_layout.addStretch()
        self.selected_pos = (1, 1)
        self.update_sliders()

    def on_gl_point_selected(self, r, c):
        # Grid 索引计算
        idx = r * self.grid_size + c
        self.combo_pts.blockSignals(True)
        self.combo_pts.setCurrentIndex(idx)
        self.combo_pts.blockSignals(False)
        self.selected_pos = (r, c)
        self.update_sliders()

    def on_mode_changed(self, mode_id, checked):
        if checked: self.gl_widget.set_render_mode(mode_id)

    def on_pt_changed(self, idx):
        self.selected_pos = self.combo_pts.itemData(idx)
        self.gl_widget.set_selected_index(*self.selected_pos)
        self.update_sliders()

    def update_sliders(self):
        r, c = self.selected_pos
        pt = self.gl_widget.control_grid[r][c]
        for s in self.sliders.values(): s.blockSignals(True)
        self.sliders['X'].setValue(int(pt.x() * 10))
        self.sliders['Y'].setValue(int(pt.y() * 10))
        self.sliders['Z'].setValue(int(pt.z() * 10))
        for s in self.sliders.values(): s.blockSignals(False)

    def on_slider_changed(self):
        r, c = self.selected_pos
        x = self.sliders['X'].value() / 10.0
        y = self.sliders['Y'].value() / 10.0
        z = self.sliders['Z'].value() / 10.0
        self.gl_widget.update_control_point(r, c, QVector3D(x, y, z))

    def on_gl_point_dragged(self, r, c, pos):
        self.selected_pos = (r, c)
        for s in self.sliders.values(): s.blockSignals(True)
        self.sliders['X'].setValue(int(pos.x() * 10))
        self.sliders['Y'].setValue(int(pos.y() * 10))
        self.sliders['Z'].setValue(int(pos.z() * 10))
        for s in self.sliders.values(): s.blockSignals(False)

