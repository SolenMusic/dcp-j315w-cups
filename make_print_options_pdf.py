#!/usr/bin/env python3
"""Create a small, redistributable PDF fixture for real CUPS option checks."""
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def create(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), invariant=1, pagesize=(595, 842))
    pdf.setTitle("Native driver print options test")
    pdf.setAuthor("DCP-J315W Native project")
    image = Image.new("RGB", (96, 64))
    colors = ((0, 128, 192), (224, 64, 96), (224, 192, 32), (32, 160, 96))
    for y in range(image.height):
        for x in range(image.width):
            image.putpixel((x, y), colors[(x // 24 + y // 16) % 4])
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    picture = ImageReader(buffer)
    for page, (width, height) in enumerate(((595, 842), (595, 842),
                                           (842, 595), (1190, 1684)), 1):
        pdf.setPageSize((width, height))
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setLineWidth(1)
        pdf.rect(36, 36, width - 72, height - 72)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(60, height - 76, f"PRINT OPTIONS - SOURCE PAGE {page} OF 4")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(60, height - 99, f"PDF page: {width} x {height} points")
        pdf.drawString(60, height - 120, "Text, image, orientation and page-selection check.")
        pdf.drawString(60, height - 141, "The complete outer frame should remain visible when fitted.")
        pdf.drawImage(picture, 60, height - 240, width=96, height=64)
        # Distinct black page identifiers also survive monochrome rasterization.
        pdf.rect(180, height - 210, page * 24, 24, fill=1, stroke=0)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(60, 52, f"BOTTOM LEFT - PAGE {page}")
        pdf.drawRightString(width - 60, 52, "BOTTOM RIGHT")
        pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    create(sys.argv[1])
