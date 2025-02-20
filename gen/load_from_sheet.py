import os
from PIL import Image, ImageTk
import numpy as np
from math import floor
import tkinter as tk
from tkinter import filedialog

def make_transparent(image):
    image = image.convert("RGBA")
    datas = image.getdata()

    new_data = []
    top_left_pixel = datas[0]

    for item in datas:
        if item[:4] == top_left_pixel[:4]:
            new_data.append((255, 255, 255, 0))  # Set transparent
        else:
            new_data.append(item)

    image.putdata(new_data)
    return image

def image_region_split(image):
    regions = np.zeros((image.width, image.height))
    visited = np.zeros((image.width, image.height))
    region = 1
    regionsStats = {}

    px = image.load()

    def visit(x, y):
        stack = [(x, y)]
        points = 0

        while stack:
            cx, cy = stack.pop()
            if cx < 0 or cy < 0 or cx >= image.width or cy >= image.height:
                continue
            if visited[cx, cy] == 1:
                continue
            visited[cx, cy] = 1
            if px[cx, cy][3] == 0:
                continue
            regions[cx, cy] = region
            points += 1
            for xd in range(cx - 1, cx + 2):
                for yd in range(cy - 1, cy + 2):
                    stack.append((xd, yd))

        return points

    for x in range(image.width):
        for y in range(image.height):
            if visited[x, y] == 0 and px[x, y][3] != 0:
                points = visit(x, y)
                regionsStats[region] = max(points, regionsStats[region]) if region in regionsStats else points
                if points > 0:
                    region += 1

    return regions, regionsStats


def get_region_bounds(region_map, region_id):
    # Find the indices where the region_id is located
    indices = np.argwhere(region_map == region_id)
    
    if indices.size == 0:
        return None  # Region ID not found in the region map

    # Get the minimum and maximum x and y coordinates
    min_x, min_y = np.min(indices, axis=0)
    max_x, max_y = np.max(indices, axis=0)

    # Return the bounds as (min_x, min_y, max_x, max_y)
    return min_x, min_y, max_x+1, max_y+1


def maximize_overlap(sheet, frame_a, frame_b, offset_range=7):
    if not frame_a or not frame_b or frame_a == (0,0,0,0) or frame_b == (0,0,0,0):
        return (0,0)

    # Convert images to numpy arrays
    img_a = np.array(sheet.crop(frame_a))[:,:,3] > 0  # Get alpha channel and convert to boolean mask
    img_b = np.array(sheet.crop(frame_b))[:,:,3] > 0

    area = float("inf")
    best_offset = (0, 0)
    
    for offset_x in range(-offset_range, offset_range+1):
        for offset_y in range(-offset_range, offset_range+1):
            # Create padded arrays
            h = max(img_a.shape[0], img_b.shape[0]) + abs(offset_y)
            w = max(img_a.shape[1], img_b.shape[1]) + abs(offset_x)
            
            canvas_a = np.zeros((h, w), dtype=bool)
            canvas_b = np.zeros((h, w), dtype=bool)
            
            # Place images with offset
            ya = max(0-offset_y, 0)
            xa = max(0-offset_x, 0)
            yb = max(0+offset_y, 0)
            xb = max(0+offset_x, 0)
            
            canvas_a[ya:ya+img_a.shape[0], xa:xa+img_a.shape[1]] = img_a
            canvas_b[yb:yb+img_b.shape[0], xb:xb+img_b.shape[1]] = img_b
            
            # Calculate overlap
            overlap = np.sum(canvas_a | canvas_b)  # Count total pixels after union
            
            if overlap < area:
                area = overlap
                best_offset = (offset_x, offset_y)
                
    return best_offset


def fix_overlap(offsets):
    for r in range(4):
        offsets[r][0] = list(offsets[r][0])
        offsets[r][1] = list(offsets[r][1])
        offsets[r][2] = list(offsets[r][2])
        for i in (0,1):
            if offsets[r][1][i] < 0 and offsets[r][2][i] < 0:
                same = min(abs(offsets[r][1][i]), abs(offsets[r][2][i]))
                offsets[r][1][i] += same
                offsets[r][2][i] += same
                offsets[r][0][i] = same
            if offsets[r][1][i] > 0 and offsets[r][2][i] > 0:
                same = min(abs(offsets[r][1][i]), abs(offsets[r][2][i]))
                offsets[r][1][i] -= same
                offsets[r][2][i] -= same
                offsets[r][0][i] = -same
        offsets[r][0] = tuple(offsets[r][0])
        offsets[r][1] = tuple(offsets[r][1])
        offsets[r][2] = tuple(offsets[r][2])
    return offsets


def make_anim_from_frames(sheet, frames):
    frame_width = max(max_x - min_x for framerow in frames for min_x, min_y, max_x, max_y in framerow) + 2
    frame_height = max(max_y - min_y for framerow in frames for min_x, min_y, max_x, max_y in framerow) + 2
    frame_offsets = [[(0,0)]+[maximize_overlap(sheet, frames[r][0], frames[r][c]) for c in range(1,3)] for r in range(4)]
    print("pre-normal", frame_offsets)
    frame_offsets = fix_overlap(frame_offsets)
    print("post-normal", frame_offsets)
    left_pad = -min(offset_x for row in frame_offsets for offset_x, offset_y in row)
    top_pad = -min(offset_y for row in frame_offsets for offset_x, offset_y in row)
    right_pad = max(offset_x for row in frame_offsets for offset_x, offset_y in row)
    bottom_pad = max(offset_y for row in frame_offsets for offset_x, offset_y in row)
    # redefined frame_width and frame_height to account for padding
    frame_width += left_pad + right_pad
    frame_height += top_pad + bottom_pad
    anim_image = Image.new("RGBA", (frame_width * 3, frame_height * 4), (0,0,0,0))

    for i, framerow in enumerate(frames):
        for j, frame in enumerate(framerow):
            min_x, min_y, max_x, max_y = frame
            frame_img = sheet.crop((min_x, min_y, max_x, max_y))
            anim_image.paste(frame_img, (j * frame_width + left_pad + frame_offsets[i][j][0], i * frame_height + top_pad + frame_offsets[i][j][1]))
    
    return anim_image


def to_square(img):
    n = max(img.width, img.height)
    if n == img.width and n == img.height:
        return img
    dx = floor((n - img.width) / 2)
    dy = floor((n - img.height) / 2)
    result = Image.new("RGBA", (n, n), (0,0,0,0))
    result.paste(img, (dx, dy))
    return result


class ImageApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sheet Splitter")
        
        self.canvas = tk.Canvas(root, width=900, height=900)
        self.canvas.pack()

        self.load_image_button = tk.Button(root, text="Save", font=("Helvetica", 30), bg="green", command=self.confirm_image)
        self.clear_button = tk.Button(root, text="Clear", font=("Helvetica", 30), bg="purple", command=self.clear_image)
        self.error_button = tk.Button(root, text="Discard", font=("Helvetica", 30), bg="red", command=self.error_image)
        self.load_image_button.pack(side=tk.RIGHT)
        self.clear_button.pack(side=tk.RIGHT)
        self.error_button.pack(side=tk.RIGHT)
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.imagePaths = []
        directory = filedialog.askdirectory(
            title='Select Directory',
            initialdir='.'  # starts in current directory
        )
        if not directory:
            print("No directory selected!")
            exit(1)
        for root, _, files in os.walk(directory):
            for file in files:
                base = os.path.basename(file)
                base = base[:base.rfind(".")]
                if os.path.exists(os.path.join("images", "digimon-overworld", f"{base}.png")) and os.path.exists(os.path.join("images", "digimon-profile", f"{base}.png")):
                    continue
                if file.endswith(".png") or file.endswith(".webp"):
                    self.imagePaths.append(os.path.join(root, file))
        
        self.frames = [[(0,0,0,0) for _ in range(3)] for _ in range(4)]
        self.select_pointer = (0,0)
        self.next_image()

        self.walk = 0
        self.update_rotater()

    def on_canvas_click(self, event):
        # Check if the click is within the bounds of the sheet image
        if 5 <= event.x <= self.sheet_width + 5 and 5 <= event.y <= self.sheet_height + 5:
            pixel_x = int((event.x - 5) * self.sheet.width / self.sheet_width)
            pixel_y = int((event.y - 5) * self.sheet.height / self.sheet_height)
            print("Sheet image clicked at:", event.x, event.y, "Pixel coordinates:", pixel_x, pixel_y)
            
            # get the region of the clicked pixel
            region = self.sheet_regions[pixel_x, pixel_y]
            print("Region:", region)

            if region == 0:
                return
            
            if self.select_pointer == "portrait":
                self.portrait = self.sheet.crop(get_region_bounds(self.sheet_regions, region))
                self.redraw()
                self.select_pointer = (0,0)
                return

            # get the next frame row
            self.frames[self.select_pointer[0]][self.select_pointer[1]] = get_region_bounds(self.sheet_regions, region)
            self.select_pointer = (self.select_pointer[0], self.select_pointer[1] + 1)
            if self.select_pointer[1] == 3:
                self.select_pointer = (self.select_pointer[0] + 1, 0)
            if self.select_pointer[0] == 4:
                self.select_pointer = "portrait"
            print(self.frames)
            self.redraw()

    def load_sheet(self):
        if self.file_path:
            self.sheet = Image.open(self.file_path)
            self.sheet = make_transparent(self.sheet)
            self.sheet_regions, self.sheet_region_info = image_region_split(self.sheet)

            portrait_region = max(self.sheet_region_info, key=self.sheet_region_info.get)
            profile_bounds = get_region_bounds(self.sheet_regions, portrait_region)
            self.portrait = self.sheet.crop(profile_bounds)
            self.frames = [[(0,0,0,0) for _ in range(3)] for _ in range(4)]
            self.frame_image = None
            self.frame_photo = None

            self.redraw()
        else:
            exit(0)


    def redraw(self):
        # draw the sheet
        if self.sheet.height > self.sheet.width:
            self.sheet_width = int(400 * self.sheet.width / self.sheet.height)
            self.sheet_height = 400
        else:
            self.sheet_width = 400
            self.sheet_height = int(400 * self.sheet.height / self.sheet.width)
        self.sheet_photo = ImageTk.PhotoImage(self.sheet.resize((self.sheet_width, self.sheet_height), Image.NEAREST))
        self.canvas.create_image(5, 5, anchor=tk.NW, image=self.sheet_photo)

        # draw the portrait
        if self.portrait:
            self.portrait_photo = ImageTk.PhotoImage(self.portrait.resize((int(400 * self.portrait.width / self.portrait.height), 400), Image.NEAREST))
            self.canvas.create_image(405, 5, anchor=tk.NW, image=self.portrait_photo)

        # draw the frames
        if self.frames:
            self.frame_image = make_anim_from_frames(self.sheet, self.frames)
            self.frame_photo = ImageTk.PhotoImage(self.frame_image.resize((int(400 * self.frame_image.width / self.frame_image.height), 400), Image.NEAREST))
            self.canvas.create_image(405, 405, anchor=tk.NW, image=self.frame_photo)

    def confirm_image(self):
        overworld = make_anim_from_frames(self.sheet, self.frames)
        fname = os.path.split(self.file_path)[1]
        fname = fname[:fname.rfind(".")]
        overworld.save(os.path.join("images", "digimon-overworld", f"{fname}.png"))
        profile = to_square(self.portrait)
        profile.save(os.path.join("images", "digimon-profile", f"{fname}.png"))
        os.remove(self.file_path)
        self.next_image()

    def error_image(self):
        # os.remove(self.file_path)
        self.frames = []
        self.next_image()
    
    def clear_image(self):
        self.frames = [[(0,0,0,0) for _ in range(3)] for _ in range(4)]
        self.select_pointer = "portrait"
        self.portrait = None
        self.portrait_photo = None
        self.frame_image = None
        self.frame_photo = None
        self.rotate_photo = None
        self.redraw()
    
    def next_image(self):
        if not self.imagePaths:
            exit(0)
        self.file_path = self.imagePaths.pop(0)
        self.load_sheet()
    
    def update_rotater(self):
        if self.file_path:
            try:
                rotate_idx = floor((self.walk // 40) % 4)
                frame_idx = floor((self.walk // 10) % 3)

                frame_width = self.frame_image.width // 3
                frame_height = self.frame_image.height // 4

                rotate_image = self.frame_image.crop((
                    frame_idx * frame_width,
                    rotate_idx * frame_height,
                    (frame_idx + 1) * frame_width,
                    (rotate_idx + 1) * frame_height)
                )
                if self.walk < 40:
                    x = self.walk
                    y = self.walk + 40
                elif self.walk < 80:
                    x = self.walk
                    y = -self.walk + 120
                elif self.walk < 120:
                    x = -self.walk + 160
                    y = -self.walk + 120
                else:
                    x = -self.walk + 160
                    y = self.walk - 120
                x = floor(x / 10 * frame_width)
                y = floor(y / 10 * frame_width)
                self.rotate_photo = ImageTk.PhotoImage(rotate_image.resize((rotate_image.width * 4, rotate_image.height * 4), Image.NEAREST))
                self.canvas.create_image(5 + x, 450 + y, anchor=tk.NW, image=self.rotate_photo)
                self.walk = (self.walk + 1) % (40 * 4)
            except Exception as e:
                print(e)
            self.root.after(20, self.update_rotater)

if __name__ == "__main__":
    os.makedirs(os.path.join("images","digimon-overworld"), exist_ok=True)
    os.makedirs(os.path.join("images","digimon-profile"), exist_ok=True)
    root = tk.Tk()
    app = ImageApp(root)
    root.mainloop()

