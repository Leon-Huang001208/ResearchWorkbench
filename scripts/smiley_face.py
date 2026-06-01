#!/usr/bin/env python3
"""Smiley Face macOS App - 用 tkinter 画一个笑脸"""

import tkinter as tk
import math


class SmileyFace(tk.Canvas):
    """画笑脸的 Canvas"""

    def __init__(self, master, size=400):
        super().__init__(master, width=size, height=size, bg="white", highlightthickness=0)
        self.size = size
        self.pack()

        # 等窗口渲染后再画
        self.after(50, self.draw)

    def draw(self):
        s = self.size
        cx, cy = s / 2, s / 2
        r = s * 0.38  # 脸半径

        # --- 脸（黄色圆） ---
        self.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#FFD700", outline="black", width=3,
        )

        # --- 左眼 ---
        eye_r = r * 0.15
        eye_y = cy - r * 0.25
        left_x = cx - r * 0.35
        right_x = cx + r * 0.35
        self.create_oval(
            left_x - eye_r, eye_y - eye_r,
            left_x + eye_r, eye_y + eye_r,
            fill="black",
        )

        # --- 右眼 ---
        self.create_oval(
            right_x - eye_r, eye_y - eye_r,
            right_x + eye_r, eye_y + eye_r,
            fill="black",
        )

        # --- 嘴巴（弧线） ---
        mouth_r = r * 0.55
        mouth_y = cy - r * 0.05
        # 画弧线: 220° 到 320°（下半圆偏上）
        start_angle = 220
        extent = 100  # 320 - 220
        self.create_arc(
            cx - mouth_r, mouth_y - mouth_r * 0.5,
            cx + mouth_r, mouth_y + mouth_r * 0.5,
            start=start_angle, extent=extent,
            style="arc", outline="black", width=3,
        )

        # --- 左腮红 ---
        blush_r = r * 0.2
        blush_y = cy + r * 0.05
        for bx, color in [(cx - r * 0.5, "#FFB6C1"), (cx + r * 0.5, "#FFB6C1")]:
            self.create_oval(
                bx - blush_r, blush_y - blush_r * 0.6,
                bx + blush_r, blush_y + blush_r * 0.6,
                fill=color, outline="",
            )


def main():
    root = tk.Tk()
    root.title("😊 Smiley Face")
    root.resizable(False, False)

    SmileyFace(root, size=400)

    # 居中显示
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    root.mainloop()


if __name__ == "__main__":
    main()
