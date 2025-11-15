# 矢量图基类
from PyQt6.QtCore import QPointF

class VectorShape:
    def __init__(self, shape_type, border_color, fill_color):
        self.type = shape_type
        self.border_color = border_color
        self.fill_color = fill_color
        self.line_style = 'solid'   # 'solid' or 'dash'
        self.angle = 0.0

    def contains(self, point:QPointF):
        """处理点击"""
        pass

    def translate(self, dx, dy):
        """以 image 坐标移动 shape（修改内部坐标）"""
        raise NotImplementedError

    def rotate(self, angle_deg, center: QPointF = None):
        """以 center 为旋转中心（image 坐标），angle_deg 增量旋转"""
        raise NotImplementedError

# 线段矢量图
class LineShape(VectorShape):
    def __init__(self, p1, p2, border_color):
        super().__init__('Line', border_color, None)
        self.p1 = QPointF(p1)
        self.p2 = QPointF(p2)

    def get_line(self):
        return [(self.p1.x(), self.p1.y(), self.p2.x(), self.p2.y())]

    def contains(self, point:QPointF):
        pass  # 直线不处理点击

# 多边形矢量图
# 存储按边的顺序排列的点
class PolygonShape(VectorShape):
    def __init__(self, points, border_color, fill_color=None):
        super().__init__('Polygon', border_color, fill_color)
        self.points = [QPointF(p) for p in points]

    def get_edges(self):
        edges = []
        n = len(self.points)
        for i in range(n):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % n]
            edges.append((p1.x(), p1.y(), p2.x(), p2.y()))
        return edges

    def contains(self, point:QPointF):
        x = point.x()
        y = point.y()
        intersections = 0
        pts = self.points
        for i in range(len(pts)):
            x1, y1 = pts[i].x(), pts[i].y()
            x2, y2 = pts[(i + 1) % len(pts)].x(), pts[(i + 1) % len(pts)].y()

            if (y1 > y) != (y2 > y):
                x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x_intersect >= x:
                    intersections += 1
        return intersections % 2 == 1

# 椭圆矢量图
# 存储绘制椭圆时矩形的左上方和右下方点坐标，以及
# 没有边表的说法，通过椭圆定义来进行扫描线填充
class EllipseShape(VectorShape):
    def __init__(self, p1, p2, border_color, fill_color=None):
        super().__init__('Ellipse', border_color, fill_color)
        self.centre = QPointF((p1.x()+p2.x())/2.0, (p1.y()+p2.y())/2.0)
        self.a = abs((p2.x() - p1.x())/2.0)
        self.b = abs((p1.y() - p2.y())/2.0)


    def contains(self, point:QPointF):
        # 相对椭圆中心的坐标
        x = point.x() - self.centre.x()
        y = point.y() - self.centre.y()

        x2 = x**2
        y2 = y**2
        a2 = self.a**2
        b2 = self.b**2
        return b2*x2 + a2 *y2 <= a2*b2

# 圆形矢量图
# 存储中心点和半径
class CircleShape(VectorShape):
    def __init__(self, centre, radius, border_color, fill_color=None):
        super().__init__('Circle', border_color, fill_color)
        self.centre = centre
        self.radius = radius

    def contains(self, point:QPointF):
        x = point.x()-self.centre.x()
        y = point.y()-self.centre.y()
        return x**2 + y**2 <= self.radius**2

