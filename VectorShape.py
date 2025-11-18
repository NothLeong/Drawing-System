# 矢量图基类
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from Transform import Transform
class VectorShape:
    def __init__(self, shape_type, border_color, fill_color, line_style='solid'):
        self.type = shape_type
        self.border_color = border_color
        self.fill_color = fill_color
        self.line_style = line_style   # 'solid' or 'dash'
        self.angle = 0.0
        self.centre = None

    def contains(self, point:QPointF):
        """处理点击"""
        pass

    def rotate(self, angle):
        raise NotImplementedError

    def get_centre(self):
        return self.centre

    def drag_and_drop(self, dx, dy):
        raise NotImplementedError

# 线段矢量图
class LineShape(VectorShape):
    def __init__(self, p1, p2, border_color, line_style='solid'):
        super().__init__('Line', border_color, None, line_style)
        self.p1 = QPointF(p1)
        self.p2 = QPointF(p2)
        self.centre = QPointF((p1.x()+p2.x())/2.0, (p1.y()+p2.y())/2.0)

    def get_line(self):
        return [(self.p1.x(), self.p1.y(), self.p2.x(), self.p2.y())]

    def contains(self, point:QPointF):
        # 判断点到线段距离 < 若干像素
        px, py = point.x(), point.y()
        x1, y1 = self.p1.x(), self.p1.y()
        x2, y2 = self.p2.x(), self.p2.y()
        threshold = 3.0  # 点击误差

        # 计算点到线段距离
        from tool import point_to_segment
        dist = point_to_segment(point, self.p1, self.p2)
        return dist <= threshold

    def rotate(self, angle):
        self.p1 = Transform.rotate_point(self.p1, self.centre, angle)
        self.p2 = Transform.rotate_point(self.p2, self.centre, angle)
        self.angle += angle

    def drag_and_drop(self, dx, dy):
        self.centre = QPointF(self.centre.x()+dx, self.centre.y()+dy)
        self.p1 = Transform.dad_point(self.p1, dx, dy)
        self.p2 = Transform.dad_point(self.p2, dx, dy)
# 多边形矢量图
# 存储按边的顺序排列的点
class PolygonShape(VectorShape):
    def __init__(self, points, border_color, fill_color=None, line_style='solid'):
        super().__init__('Polygon', border_color, fill_color, line_style)
        self.points = [p for p in points]
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        self.centre = QPointF(sum(xs)/len(xs), sum(ys)/len(ys))

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

    def rotate(self, angle):
        self.points = Transform.rotate_points(self.points, self.centre, angle)
        self.angle += angle
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        self.centre = QPointF(sum(xs) / len(xs), sum(ys) / len(ys))

    def drag_and_drop(self, dx, dy):
        self.centre = QPointF(self.centre.x() + dx, self.centre.y() + dy)
        self.points = Transform.dad_points(self.points, dx, dy)

# 椭圆矢量图
# 存储绘制椭圆时矩形的左上方和右下方点坐标，以及
# 没有边表的说法，通过椭圆定义来进行扫描线填充
class EllipseShape(VectorShape):
    def __init__(self, p1, p2, border_color, fill_color=None, line_style='solid'):
        super().__init__('Ellipse', border_color, fill_color, line_style)
        self.centre = QPointF((p1.x()+p2.x())/2.0, (p1.y()+p2.y())/2.0)
        self.a = abs((p2.x() - p1.x())/2.0)
        self.b = abs((p1.y() - p2.y())/2.0)

    def contains(self, point: QPointF):
        # 相对椭圆中心的坐标
        x = point.x() - self.centre.x()
        y = point.y() - self.centre.y()

        # 考虑旋转角度（angle 以度为单位）
        import math
        cosA = math.cos(math.radians(-getattr(self, 'angle', 0.0)))  # 反旋转
        sinA = math.sin(math.radians(-getattr(self, 'angle', 0.0)))

        # 将点旋转回未旋转的椭圆坐标系
        x_un = x * cosA - y * sinA
        y_un = x * sinA + y * cosA

        # 椭圆公式判断
        a2 = self.a ** 2
        b2 = self.b ** 2
        return (x_un ** 2) / a2 + (y_un ** 2) / b2 <= 1.0

    def rotate(self, angle):
        self.angle += angle

    def drag_and_drop(self, dx, dy):
        self.centre = QPointF(self.centre.x() + dx, self.centre.y() + dy)

# 圆形矢量图
# 存储中心点和半径
class CircleShape(VectorShape):
    def __init__(self, centre, radius, border_color, fill_color=None, line_style='solid'):
        super().__init__('Circle', border_color, fill_color, line_style)
        self.centre = centre
        self.radius = radius

    def contains(self, point:QPointF):
        x = point.x()-self.centre.x()
        y = point.y()-self.centre.y()
        return x**2 + y**2 <= self.radius**2

    def rotate(self, angle):
        self.angle += angle

    def drag_and_drop(self, dx, dy):
        self.centre = QPointF(self.centre.x()+dx, self.centre.y()+dy)

