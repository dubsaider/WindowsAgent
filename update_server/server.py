"""
Простой HTTP сервер для дистрибуции обновлений PC-Guardian Agent.

Использование:
    python -m update_server.server --port 8000 --exe-dir ../dist --version-file version.json

Сервер предоставляет два эндпоинта:
    GET /updates/version.json - информация о последней версии
    GET /updates/PCGuardianAgent.exe - скачивание exe файла
"""

import os
import sys
import json
import argparse
import http.server
import socketserver
from pathlib import Path
from urllib.parse import urlparse


class UpdateServerHandler(http.server.SimpleHTTPRequestHandler):
    """Обработчик запросов для сервера обновлений"""
    
    def __init__(self, *args, exe_dir=None, version_file=None, **kwargs):
        self.exe_dir = Path(exe_dir) if exe_dir else None
        self.version_file = Path(version_file) if version_file else None
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Эндпоинт для получения информации о версии
        if path == '/updates/version.json' or path == '/version.json':
            self.serve_version_info()
        # Эндпоинт для скачивания exe
        elif path == '/updates/PCGuardianAgent.exe' or path == '/PCGuardianAgent.exe':
            self.serve_exe_file()
        else:
            self.send_error(404, "Not Found")
    
    def serve_version_info(self):
        """Отдаёт информацию о последней версии"""
        try:
            if self.version_file and self.version_file.exists():
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    version_data = json.load(f)
            else:
                # Генерируем версию на основе файла __version__.py из корня проекта
                version_data = self._generate_version_info()
            
            response = json.dumps(version_data, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Error loading version info: {e}")
    
    def serve_exe_file(self):
        """Отдаёт exe файл для скачивания"""
        try:
            if not self.exe_dir:
                self.send_error(500, "EXE directory not configured")
                return
            
            exe_path = self.exe_dir / 'PCGuardianAgent.exe'
            if not exe_path.exists():
                self.send_error(404, "PCGuardianAgent.exe not found")
                return
            
            file_size = exe_path.stat().st_size
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="PCGuardianAgent.exe"')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()
            
            with open(exe_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            self.send_error(500, f"Error serving exe file: {e}")
    
    def _generate_version_info(self):
        """Генерирует информацию о версии из __version__.py"""
        try:
            # Пытаемся импортировать версию из корня проекта
            project_root = Path(__file__).parent.parent
            sys.path.insert(0, str(project_root))
            from __version__ import __version__
            
            # Определяем URL для скачивания (на основе текущего запроса)
            host = self.headers.get('Host', 'localhost:8000')
            download_url = f"http://{host}/updates/PCGuardianAgent.exe"
            
            return {
                "version": __version__,
                "download_url": download_url
            }
        except Exception:
            # Если не удалось получить версию, возвращаем заглушку
            host = self.headers.get('Host', 'localhost:8000')
            download_url = f"http://{host}/updates/PCGuardianAgent.exe"
            return {
                "version": "1.0.0",
                "download_url": download_url
            }
    
    def log_message(self, format, *args):
        """Переопределяем логирование для более информативного вывода"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def create_handler(exe_dir, version_file):
    """Создаёт обработчик с нужными параметрами"""
    def handler(*args, **kwargs):
        return UpdateServerHandler(*args, exe_dir=exe_dir, version_file=version_file, **kwargs)
    return handler


def main():
    parser = argparse.ArgumentParser(description='PC-Guardian Update Server')
    parser.add_argument('--port', type=int, default=8000, help='Порт сервера (по умолчанию 8000)')
    parser.add_argument('--exe-dir', type=str, default='../dist', 
                       help='Директория с exe файлом (по умолчанию ../dist)')
    parser.add_argument('--version-file', type=str, default=None,
                       help='Путь к JSON файлу с информацией о версии (опционально)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Хост для прослушивания (по умолчанию 0.0.0.0)')
    
    args = parser.parse_args()
    
    exe_dir = Path(args.exe_dir).resolve()
    if not exe_dir.exists():
        print(f"ОШИБКА: Директория {exe_dir} не существует")
        sys.exit(1)
    
    exe_path = exe_dir / 'PCGuardianAgent.exe'
    if not exe_path.exists():
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл {exe_path} не найден")
    
    version_file = Path(args.version_file).resolve() if args.version_file else None
    if version_file and not version_file.exists():
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл версии {version_file} не найден, будет использована версия из __version__.py")
        version_file = None
    
    handler = create_handler(exe_dir, version_file)
    
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"Сервер обновлений запущен на http://{args.host}:{args.port}")
        print(f"EXE директория: {exe_dir}")
        if version_file:
            print(f"Файл версии: {version_file}")
        print(f"\nЭндпоинты:")
        print(f"  GET http://{args.host}:{args.port}/updates/version.json")
        print(f"  GET http://{args.host}:{args.port}/updates/PCGuardianAgent.exe")
        print("\nНажмите Ctrl+C для остановки")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nОстановка сервера...")


if __name__ == '__main__':
    main()

