# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# 获取平台特定的可执行文件名
if sys.platform == "win32":
    exe_name = 'pan115-scraper-win'
elif sys.platform == "darwin":
    exe_name = 'pan115-scraper-mac'
else:
    exe_name = 'pan115-scraper-linux'

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('config.json.example', '.'),
        ('README.md', '.'),
        ('LICENSE', '.'),
    ],
    hiddenimports=[
        # 加密相关
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.serialization',

        # Flask相关
        'flask',
        'flask.templating',
        'flask.json',
        'flask.helpers',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.utils',
        'jinja2',
        'jinja2.ext',
        'markupsafe',

        # 网络请求相关
        'requests',
        'requests.packages',
        'requests.packages.urllib3',
        'requests.packages.urllib3.util',
        'requests.packages.urllib3.util.retry',
        'urllib3',
        'urllib3.packages',
        'urllib3.packages.six',
        'urllib3.util',
        'urllib3.util.retry',
        'urllib3.connection',
        'urllib3.connectionpool',
        'urllib3.poolmanager',

        # 标准库
        'sqlite3',
        'json',
        'logging',
        'logging.handlers',
        'threading',
        'queue',
        'time',
        'datetime',
        'hashlib',
        'base64',
        'os',
        'os.path',
        'stat',
        'uuid',
        're',
        'urllib.parse',
        'concurrent.futures',
        'email.mime.multipart',
        'email.mime.text',
        'email.mime.base',
        'email.encoders',

        # 其他依赖
        'six',
        'six.moves',
        'six.moves.urllib',
        'six.moves.urllib.parse',
        'certifi',
        'charset_normalizer',
        'idna',
    ],
    hookspath=['.'],  # 包含当前目录的hook文件
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI框架
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',

        # 科学计算库
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        'keras',

        # 图像处理
        'PIL',
        'Pillow',
        'cv2',
        'opencv',

        # 其他大型库
        'jupyter',
        'notebook',
        'IPython',
        'sympy',
        'statsmodels',
    ],
    noarchive=False,
    optimize=1,  # 启用优化
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # 保持False以便调试
    upx=True,     # 启用UPX压缩
    upx_exclude=[
        # 排除一些可能导致问题的库
        'vcruntime140.dll',
        'python3.dll',
        'python312.dll',
    ],
    runtime_tmpdir=None,
    console=True,  # 保持控制台窗口以便查看日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
    version=None,  # 可以添加版本信息文件
)

# macOS特定配置
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name='pan115scraper-scraper.app',
        icon=None,
        bundle_identifier='com.pan115scraper.app',
        info_plist={
            'CFBundleName': 'pan115scraper',
            'CFBundleDisplayName': 'pan115scraper-scraper',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleIdentifier': 'com.pan115scraper.app',
            'NSHighResolutionCapable': True,
            'LSUIElement': False,
        },
    )
