"""Convert PNG icon to ICO format for Windows executable"""
from PIL import Image
import sys

def convert_png_to_ico(png_path, ico_path):
    """Convert PNG to ICO with multiple sizes for Windows"""
    img = Image.open(png_path)

    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Create multiple sizes for the ICO file
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # Resize and save
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"Icon saved to {ico_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_icon.py <input.png> [output.ico]")
        sys.exit(1)

    png_path = sys.argv[1]
    ico_path = sys.argv[2] if len(sys.argv) > 2 else "icon.ico"
    convert_png_to_ico(png_path, ico_path)
