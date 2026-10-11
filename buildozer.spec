[app]

title = たすくえ
package.name = taskue
package.domain = org.example
source.dir = .
source.include_exts = py,png
source.include_patterns = assets/*.png
source.exclude_dirs = .git,.venv,.venv-1,__pycache__,.streamlit,.vscode,build,bin
source.exclude_patterns = app.py,*.db,*.sqlite,*.sqlite3
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.presplash.filename = %(source.dir)s/assets/ローディング.png
android.api = 31
android.minapi = 28
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE

[buildozer]
log_level = 2
warn_on_root = 1
