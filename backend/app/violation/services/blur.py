"""Selective blur: blur whole frame, keep only violating vehicle bboxes unblurred."""
from __future__ import annotations

from app.violation.utils.image import gaussian_blur, paste_bbox


class BlurService:
    def __init__(self, blur_kernel_size: int = 51):
        """blur_kernel_size: 3=barely visible, 51=strong privacy blur. Must be odd."""
        self.blur_kernel_size = blur_kernel_size if blur_kernel_size % 2 == 1 else blur_kernel_size + 1

    def selectively_unblur(self, frame, keep_bboxes: list[tuple[int, int, int, int]]):
        output = gaussian_blur(frame, kernel_size=self.blur_kernel_size)
        for bbox in keep_bboxes:
            paste_bbox(output, frame, bbox)
        return output
