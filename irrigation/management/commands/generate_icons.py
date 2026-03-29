from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw
import os


class Command(BaseCommand):
    help = 'Generate missing icon files'

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icons_dir = os.path.join(base_dir,'static', 'irrigation', 'images')

        os.makedirs(icons_dir, exist_ok=True)

        # Generate different icon sizes
        sizes = [192, 512, 144, 96, 72]

        for size in sizes:
            filename = os.path.join(icons_dir, f'icon-{size}x{size}.png')

            # Create a simple green icon with a water drop
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Draw background circle
            circle_margin = size * 0.1
            circle_size = size - (circle_margin * 2)
            draw.ellipse(
                [circle_margin, circle_margin, circle_margin + circle_size, circle_margin + circle_size],
                fill=(16, 185, 129)  # Green color
            )

            # Draw water drop
            drop_size = circle_size * 0.6
            drop_x = size / 2
            drop_y = size / 2 + drop_size * 0.1

            # Simple water drop shape
            points = [
                (drop_x, drop_y - drop_size / 2),  # Top
                (drop_x - drop_size / 3, drop_y),  # Left
                (drop_x, drop_y + drop_size / 2),  # Bottom
                (drop_x + drop_size / 3, drop_y),  # Right
            ]

            draw.polygon(points, fill=(255, 255, 255, 200))

            img.save(filename)
            self.stdout.write(f'Generated: {filename}')

        self.stdout.write('Icons generated successfully!')
