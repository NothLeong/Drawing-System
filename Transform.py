import math
from PySide6.QtCore import QPointF

class Transform:
    @staticmethod
    def rotate_point(point: QPointF, center: QPointF, angle_deg: float) -> QPointF:
        """绕 center 点旋转 angle_deg"""
        rad = math.radians(angle_deg)
        s, c = math.sin(rad), math.cos(rad)
        x, y = point.x() - center.x(), point.y() - center.y()
        x_new = x * c - y * s + center.x()
        y_new = x * s + y * c + center.y()
        return QPointF(x_new, y_new)

    @staticmethod
    def rotate_points(points: list[QPointF], center: QPointF, angle_deg: float) -> list[QPointF]:
        """旋转多个点"""
        return [Transform.rotate_point(p, center, angle_deg) for p in points]

    @staticmethod
    def dad_point(point: QPointF, dx: float, dy: float) -> QPointF:
        return QPointF(point.x() + dx, point.y() + dy)

    @staticmethod
    def dad_points(points: list[QPointF], dx: float, dy: float) -> list[QPointF]:
        return [Transform.dad_point(p, dx, dy) for p in points]
