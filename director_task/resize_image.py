from PIL import Image
import os
import glob

def resize_image_with_padding(input_path, output_path, scale_factor=0.5):
    """
    Resize image by scale_factor and place it in original canvas with blank space
    """
    # Open the original image
    original_img = Image.open(input_path)
    original_width, original_height = original_img.size
    
    # Calculate new size
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)
    
    # Resize the image
    resized_img = original_img.resize((new_width, new_height), Image.LANCZOS)
    
    # Create a new image with original dimensions and transparent background
    new_img = Image.new('RGBA', (original_width, original_height), (255, 255, 255, 0))
    
    # Calculate position to center the resized image
    x_offset = (original_width - new_width) // 2
    y_offset = (original_height - new_height) // 2
    
    # Paste the resized image onto the new canvas
    new_img.paste(resized_img, (x_offset, y_offset))
    
    # Save the result
    new_img.save(output_path)
    print(f"Resized image saved to: {output_path}")

def process_all_large_images():
    """
    Process all *_large.png files in the images directory
    """
    # Find all *_large.png files
    large_files = glob.glob("director_task/images/*_large.png")
    
    for large_file in large_files:
        # Extract base name without _large.png
        base_name = large_file.replace("_large.png", "")
        
        # Create medium version (half size)
        medium_file = f"{base_name}_medium.png"
        resize_image_with_padding(large_file, medium_file, scale_factor=0.5)
        
        # Create small version (quarter size of original)
        small_file = f"{base_name}_small.png"
        resize_image_with_padding(large_file, small_file, scale_factor=0.25)

if __name__ == "__main__":
    process_all_large_images()