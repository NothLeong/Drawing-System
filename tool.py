from PySide6.QtGui import QPainter, QPen

def make_rect(p1, p2):
    x = min(p1.x(), p2.x())
    y = min(p1.y(), p2.y())
    w = abs(p1.x() - p2.x())
    h = abs(p1.y() - p2.y())
    return (x, y, w, h)

def draw_line_bresenham(state, x1, y1, x2, y2, color):
    painter = QPainter(state.canvas)
    pen = QPen(color)
    painter.setPen(pen)

    # 可以用像素算法，也可以自己改用 setPixelColor
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    while True:
        state.canvas.setPixelColor(int(x1), int(y1), color)
        if int(x1) == int(x2) and int(y1) == int(y2):
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x1 += sx
        if e2 < dx:
            err += dx
            y1 += sy

def draw_circle_midpoint(state, xc, yc, r, color):
    x = 0
    y = int(r)
    p = 1 - r

    def draw_circle_points(xc, yc, x, y):
        for dx, dy in [(x, y), (-x, y), (x, -y), (-x, -y),
                       (y, x), (-y, x), (y, -x), (-y, -x)]:
            state.canvas.setPixelColor(int(xc + dx), int(yc + dy), color)

    draw_circle_points(xc, yc, x, y)
    while x < y:
        x += 1
        if p < 0:
            p += 2 * x + 1
        else:
            y -= 1
            p += 2 * (x - y) + 1
        draw_circle_points(xc, yc, x, y)

