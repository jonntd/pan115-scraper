# PyInstaller hook for pan115-scraper
# 确保所有必要的模块和资源都被包含

from PyInstaller.utils.hooks import collect_all, collect_data_files

# 收集Flask相关的所有数据
datas, binaries, hiddenimports = collect_all('flask')

# 添加额外的隐藏导入
hiddenimports += [
    'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.backends.openssl',
    'requests.packages.urllib3',
    'requests.packages.urllib3.util',
    'requests.packages.urllib3.util.retry',
    'urllib3.packages.six',
    'six.moves.urllib',
    'six.moves.urllib.parse',
    'email.mime.multipart',
    'email.mime.text',
    'email.mime.base',
    'email.encoders',
]

# 收集模板和静态文件
datas += collect_data_files('templates')
datas += collect_data_files('static')
