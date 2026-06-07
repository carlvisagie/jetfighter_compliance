import os, shutil

pairs = [
    (r"E:\JetFighter_Compliance\.vio_brief\VIO_Cursor_Brief_Package\images\source_image_03.jpeg",
     r"E:\JetFighter_Compliance\docs\assets\vio_sketch.jpeg"),
    (r"E:\JetFighter_Compliance\.vio_brief\VIO_Cursor_Brief_Package\images\source_image_31.png",
     r"E:\JetFighter_Compliance\docs\assets\vio_inadequate_prototype.png"),
]
for src, dst in pairs:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"copied {src} -> {dst}  ({os.path.getsize(dst)} bytes)")
