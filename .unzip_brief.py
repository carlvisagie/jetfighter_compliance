import os, shutil, zipfile
SRC = r"C:\Users\Carl\Downloads\VIO_Cursor_Brief_Package.zip"
DST = r"E:\JetFighter_Compliance\.vio_brief"
if os.path.isdir(DST):
    shutil.rmtree(DST)
os.makedirs(DST, exist_ok=True)
with zipfile.ZipFile(SRC) as zf:
    zf.extractall(DST)
    for n in zf.namelist():
        print(n)
