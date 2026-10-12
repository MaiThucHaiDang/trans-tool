# Cấu hình đóng gói PyInstaller.  Build:  pyinstaller dich.spec --noconfirm
# Kết quả: dist/Dich/Dich.exe (kèm thư mục _internal, phải để chung với nhau).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["dich/__main__.py"],
    pathex=["."],
    datas=[("assets/icon.ico", "assets"), ("assets/icon.png", "assets")],
    hiddenimports=collect_submodules("winrt"),
    excludes=["tkinter", "unittest", "pydoc", "PIL",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf",
              "PySide6.QtWebEngineCore", "PySide6.QtMultimedia", "PySide6.Qt3DCore"],
)

# Bỏ các thành phần Qt không dùng tới cho nhẹ (giao diện chỉ dùng QtWidgets).
UNUSED = ("opengl32sw.dll", "qt6quick", "qt6qml", "qt6pdf", "qt6virtualkeyboard",
          "libcrypto-3-x64", "libssl-3-x64", "/qpdf", "/tls/", "platforminputcontexts",
          "qt6opengl", "qt6svg", "qsvg")


def keep(entry):
    name = entry[0].replace("\\", "/").lower()
    if any(u in name for u in UNUSED):
        return False
    # Chỉ giữ bản dịch tiếng Việt của Qt (hộp thoại chọn file, nút Yes/No…).
    if "/translations/" in name and not name.rsplit("/", 1)[-1].startswith("qtbase_vi"):
        return False
    return True


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Dich",
    icon="assets/icon.ico",
    console=False,
    version="version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, name="Dich",
               upx=False)
