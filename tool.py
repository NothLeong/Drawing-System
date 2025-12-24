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

def point_to_segment(clicked_point, p1, p2):
    """
    返回 clicked_point 到线段 p1-p2 的最短距离（单位：像素）
    """

    x, y = clicked_point.x(), clicked_point.y()
    x1, y1 = p1.x(), p1.y()
    x2, y2 = p2.x(), p2.y()

    # 线段长度平方
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # p1 和 p2 重合（退化为点）
        return hypot(x - x1, y - y1)

    # 投影 t 参数（0~1 落在线段上）
    t = ((x - x1) * dx + (y - y1) * dy) / seg_len_sq

    # 限定 t 到线段范围
    t = max(0, min(1, t))

    # 线段上离 clicked_point 最近的点
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    # 返回距离
    return hypot(x - closest_x, y - closest_y)


# Bresenham算法，提供给RasterCanvas类的方法，在QImage上进行绘制
def draw_line_bresenham(image, x0, y0, x1, y1, color, line_style):

    painter = QPainter(image)
    pen = QPen(color)
    painter.setPen(pen)

    # ----- dash pattern -----
    if line_style == "dash":
        pattern = [1,1,1,1, 0,0,0]   # 4 实 3 空
    else:
        pattern = [1]               # 纯实线

    pi = 0                # pattern index
    plen = len(pattern)   # pattern length

    # ----- Bresenham 初始化 -----
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = int(x0), int(y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    # ----- 主算法 -----
    if dx > dy:
        err = dx / 2.0
        while x != int(x1):
            # —— 按 pattern 决定是否画点 ——
            if pattern[pi]:
                painter.drawPoint(x, y)

            pi = (pi + 1) % plen

            err -= dy
            if err < 0:
                y += sy
                err += dx

            x += sx
    else:
        err = dy / 2.0
        while y != int(y1):
            if pattern[pi]:
                painter.drawPoint(x, y)

            pi = (pi + 1) % plen

            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy

    # 处理终点
    if pattern[pi]:
        painter.drawPoint(int(x1), int(y1))
    painter.end()


# 中点圆算法
def draw_circle_midpoint(image, centre: QPointF, r, color, line_style):
    xc = int(centre.x())
    yc = int(centre.y())
    x = 0
    y = int(round(r))
    p = 1 - r

    # ---- dash pattern ----
    if line_style == "dash":
        pattern = [1,1,1,1,0,0,0]   # 可改
    else:
        pattern = [1]
    pi = 0
    plen = len(pattern)

    # ---- 根据八分之一圆弧画其他部分 ----
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

    # ---- 主循环 ----
    if pattern[pi]:
        plot(x, y)
    pi = (pi + 1) % plen

    # 主迭代
    while x < y:
        x += 1
        if p < 0:
            p += 2 * x + 1
        else:
            y -= 1
            p += 2 * (x - y) + 1

        # 这里按圆弧顺序推进 dash
        if pattern[pi]:
            plot(x, y)
        pi = (pi + 1) % plen

# 椭圆扫描转换的中点判别法
# 参数的p1为用户的开始点,p2为用户当前鼠标所在点
# 将这两个点作为矩形框，确定椭圆，进行椭圆扫描转换的扫描中点判别法
def draw_ellipse_midpoint(image, p1: QPointF, p2: QPointF, color, line_style):
    xc = int((p1.x() + p2.x()) // 2)
    yc = int((p1.y() + p2.y()) // 2)
    a = abs(int(p2.x() - p1.x())) // 2
    b = abs(int(p2.y() - p1.y())) // 2

    # ---- dash pattern ----
    if line_style == "dash":
        pattern = [1,1,1,1,0,0,0]
    else:
        pattern = [1]
    pi = 0
    plen = len(pattern)

    # ---- 考虑四分之一椭圆画对称点 ----
    def plot(x, y):
        w, h = image.width(), image.height()
        pts = [
            (xc + x, yc + y),
            (xc - x, yc + y),
            (xc + x, yc - y),
            (xc - x, yc - y),
        ]
        for px, py in pts:
            if 0 <= px < w and 0 <= py < h:
                image.setPixelColor(px, py, color)

    # ---- 初始化 ----
    x, y = 0, b
    a2 = a * a
    b2 = b * b
    d1 = b2 - a2 * b + 0.25 * a2

    # region 1： 上部分
    while b2 * x < a2 * y:

        if pattern[pi]:
            plot(x, y)
        pi = (pi + 1) % plen

        if d1 < 0:
            d1 += b2 * (2 * x + 3)
        else:
            d1 += b2 * (2 * x + 3) + a2 * (-2 * y + 2)
            y -= 1
        x += 1

    # region 2： 下部分
    d2 = b2 * (x + 0.5)**2 + a2 * (y - 1)**2 - a2 * b2

    while y >= 0:

        if pattern[pi]:
            plot(x, y)
        pi = (pi + 1) % plen

        if d2 < 0:
            d2 += b2 * (2 * x + 2) + a2 * (-2 * y + 3)
            x += 1
        else:
            d2 += a2 * (-2 * y + 3)
        y -= 1


# --- 曲线算法 ---
# ----- bezier -------
def de_casteljau(points, t):
    """de Casteljau 递推算法"""
    temp_points = [(p.x(), p.y()) for p in points]
    n = len(temp_points)
    for r in range(1, n):
        for i in range(n - r):
            x = (1 - t) * temp_points[i][0] + t * temp_points[i + 1][0]
            y = (1 - t) * temp_points[i][1] + t * temp_points[i + 1][1]
            temp_points[i] = (x, y)
    return QPointF(temp_points[0][0], temp_points[0][1])

# ---- B样条 -----
def b_spline_basis(i, k, t, knots):
    """B-样条基函数 (Cox-de Boor 递推)"""
    if k == 1:
        return 1.0 if knots[i] <= t < knots[i + 1] else 0.0

    denom1 = knots[i + k - 1] - knots[i]
    denom2 = knots[i + k] - knots[i + 1]

    val1 = 0.0
    if denom1 != 0:
        val1 = ((t - knots[i]) / denom1) * b_spline_basis(i, k - 1, t, knots)

    val2 = 0.0
    if denom2 != 0:
        val2 = ((knots[i + k] - t) / denom2) * b_spline_basis(i + 1, k - 1, t, knots)

    return val1 + val2

def calculate_b_spline_point(control_points, t, k, knots):
    """
    利用基函数计算 B-样条在参数 t 处的坐标
    P(t) = Sum(P_i * N_{i,k}(t))
    """
    n = len(control_points)
    x, y = 0.0, 0.0
    for i in range(n):
        basis = b_spline_basis(i, k, t, knots)
        x += control_points[i].x() * basis
        y += control_points[i].y() * basis
    return QPointF(x, y)

def generate_clamped_knots(n, k):
    """
    生成准均匀节点向量
    n: 控制点个数, k: 阶数 (次数+1)
    """
    # 节点个数 = n + k
    knots = [0] * k  # 开头 k 个 0
    middle_count = n - k
    for i in range(1, middle_count + 1):
        knots.append(i)

    end_val = middle_count + 1
    knots += [end_val] * k  # 结尾 k 个 end_val
    return knots


# --- 曲面算法 ---
from PySide6.QtGui import  QVector3D, QColor


def de_casteljau_3d(points, t):
    """
    3D 版 de Casteljau 算法
    points: QVector3D 列表
    t: 0.0 ~ 1.0
    """
    if not points:
        return QVector3D(0, 0, 0)

    # 创建副本，避免修改原始控制点
    temp = [QVector3D(p) for p in points]
    n = len(temp)

    # 迭代降维
    for r in range(1, n):
        for i in range(n - r):
            # 线性插值: P_new = (1-t)P_curr + t*P_next
            # QVector3D 支持这种直接的向量加减和标量乘法
            temp[i] = temp[i] * (1 - t) + temp[i + 1] * t

    return temp[0]


