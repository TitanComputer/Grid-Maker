import os
from PIL import Image, ImageDraw


def draw_grid(image_path, output_path, cols=240, rows=340, line_color=(0, 0, 0)):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Draw vertical lines
    col_width = width / cols
    for i in range(1, cols):
        x = int(i * col_width)
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)

    # Draw horizontal lines
    row_height = height / rows
    for j in range(1, rows):
        y = int(j * row_height)
        draw.line([(0, y), (width, y)], fill=line_color, width=1)

    img.save(output_path)


def main():
    input_dir = os.getcwd()
    output_dir = os.path.join(input_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith((".jpg", ".png")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            draw_grid(input_path, output_path)
            print(f"Processed: {filename}")

    print("Done. Check the 'output' folder.")


if __name__ == "__main__":
    main()
