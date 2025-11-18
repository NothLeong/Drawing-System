# 本项目通过Qt Designer软件制作UI界面,运行前请确保UI文件夹中有main.ui文件
# 帮助
## 如果想要直观比对两次大作业下不同方法的实现结果，可以使用指令输入栏
> 向指令输入栏输入指令得到的图像，是由Qt提供的绘图方法进行绘制;  
> 在Ui界面选择工具绘画得到的图像，是由本次大作业实现的光栅化算法进行绘制
# 指令输入栏现支持通过输入以下命令画图
### 
    draw point on (x,y) 在(x,y)画点
    draw line from (x1,y1) to (x2,y2) 从(x1,y1)到(x2,y2)画线段
    draw circle on (x,y) -r (radius) 以(x,y)为圆心画圆
    draw ellipse on (x,y) -a A -b B -angle ANGLE 在(x,y)处画一个长轴为A，短轴为B，倾斜角度为ANGLE的椭圆
    draw polygon (x1,y1) (x2,y2) (x3,y3) ... 画一个以这些点为顶点的多边形
    clear 清空
## 你可以通过以下指令来快速画一个小五角星！ (可以复制黏贴，支持多行输入)
    clear
    draw line from (735.11,307.10) to (581.22,418.90)
    draw line from (735.11,307.10) to (544.89,307.10)
    draw line from (640,238) to (581.22,418.90)
    draw line from (544.89,307.10) to (698.78,418.90)
    draw line from (640,238) to (698.78,418.90)
    draw circle on (640,338) -r 100
### 又或者是
    clear
    draw polygon (735.11,307.10) (581.22,418.90) (640,238) (698.78,418.90) (544.89,307.10)
    draw circle on (640,338) -r 100


