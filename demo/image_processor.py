#!/usr/bin/env python3
"""
Gerçek Hayat Örneği: Görüntü İşleme Script'i

Bu script, görüntü işleme görevini simüle eder:
- Görüntü dosyasını işler
- Dönüşümler yapar
- Metadata çıkarır
"""

import time
import json
from typing import Dict, Any


def main(params: dict, context) -> Dict[str, Any]:
    """
    Görüntü işleme fonksiyonu
    
    Args:
        params: Görev parametreleri
            - image_path: Görüntü dosya yolu
            - width: Yeni genişlik (opsiyonel)
            - height: Yeni yükseklik (opsiyonel)
            - format: Çıktı formatı (jpg, png, webp)
    
    Returns:
        dict: İşlem sonucu
    """
    image_path = params.get("image_path", "unknown.jpg")
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    format_type = params.get("format", "jpg")
    
    # Görüntü işleme simülasyonu (CPU-bound)
    # Gerçek hayatta burada PIL, OpenCV vb. kullanılır
    processing_time = 0.2  # İşleme süresi simülasyonu
    time.sleep(processing_time)
    
    # Metadata çıkar (simüle edilmiş)
    metadata = {
        "original_path": image_path,
        "dimensions": {"width": width, "height": height},
        "format": format_type,
        "file_size_kb": 1024,
        "color_space": "RGB",
        "processed": True
    }
    
    return {
        "success": True,
        "image_path": image_path,
        "output_path": f"processed_{image_path}",
        "metadata": metadata,
        "processing_time_seconds": processing_time,
        "task_id": context.task_id,
        "worker_id": context.worker_id
    }

