from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import QPointF
from math import hypot

def make_rect(p1, p2):
    x = min(p1.x(), p2.x())
    y = min(p1.y(), p2.y())
    w = abs(p1.x() - p2.x())
    h = abs(p1.y() - p2.y())
    return (x, y, w, h)

# 返回距离作为半径
def calc_radius(p1, p2):
    return hypot(p2.x() - p1.x(), p2.y() - p1.y())

# Bresenham算法，提供给RasterCanvas类的方法，在QImage上进行绘制
def draw_line_bresenham(image, x0, y0, x1, y1, color):
    painter = QPainter(image)
    pen = QPen(color)
    painter.setPen(pen)

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = int(x0), int(y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    if dx > dy:
        err = dx / 2.0
        while x != int(x1):
            painter.drawPoint(x, y)
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != int(y1):
            painter.drawPoint(x, y)
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    painter.drawPoint(int(x1), int(y1))
    painter.end()

# 中点圆算法
def draw_circle_midpoint(image, centre: QPointF, r, color):
    xc = int(centre.x())
    yc = int(centre.y())
    x = 0
    y = int(round(r))
    p = 1 - r  # 决策参数，并使用增量更新避免乘方

    # 内部绘制函数：自动绘制八个对称点
    def plot(x, y):
        w, h = image.width(), image.height()
        pts = [
            (xc + x, yc + y),
            (xc - x, yc + y),
            (xc + x, yc - y),
            (xc - x, yc - y),
            (xc + y, yc + x),
            (xc - y, yc + x),
            (xc + y, yc - x),
            (xc - y, yc - x),
        ]
        for px, py in pts:
            if 0 <= px < w and 0 <= py < h:
                image.setPixelColor(px, py, color)

    # 绘制起点
    plot(x, y)

    # 主循环，对八分之一圆弧
    while x < y:
        x += 1
        if p < 0:
            p += 2 * x + 1
        else:
            y -= 1
            p += 2 * (x - y) + 1
        plot(x, y)

# 椭圆扫描转换的中点判别法
# 参数的p1为用户的开始点,p2为用户当前鼠标所在点
# 将这两个点作为矩形框，确定椭圆，进行椭圆扫描转换的扫描中点判别法
# 缺点：不能画倾斜的椭圆
def draw_ellipse_midpoint(image, p1: QPointF, p2: QPointF, color):
    # 提取坐标并计算中心与半轴
    x0, y0 = p1.x(), p1.y()
    x1, y1 = p2.x(), p2.y()
    xc = (x0 + x1) // 2
    yc = (y0 + y1) // 2
    a = abs(x1 - x0) // 2
    b = abs(y1 - y0) // 2

    # 内部绘制函数：自动绘制四个对称点
    def plot(x, y):
        image.setPixelColor(xc + x, yc + y, color)
        image.setPixelColor(xc - x, yc + y, color)
        image.setPixelColor(xc + x, yc - y, color)
        image.setPixelColor(xc - x, yc - y, color)

    # 初始化
    x, y = 0, b
    a2 = a * a
    b2 = b * b
    d1 = b2 - a2 * b + 0.25 * a2  # 增量更新
    plot(x, y)

    # region 1： 上部分
    while b2 * (x + 1) < a2 * (y - 0.5):
        if d1 < 0:
            d1 += b2 * (2 * x + 3)
        else:
            d1 += b2 * (2 * x + 3) + a2 * (-2 * y + 2)
            y -= 1
        x += 1
        plot(x, y)

    # region 2： 下部分
    d2 = b2 * (x + 0.5) ** 2 + a2 * (y - 1) ** 2 - a2 * b2
    while y > 0:
        if d2 < 0:
            d2 += b2 * (2 * x + 2) + a2 * (-2 * y + 3)
            x += 1
        else:
            d2 += a2 * (-2 * y + 3)
        y -= 1
        plot(x, y)

