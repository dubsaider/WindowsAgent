"""
Модуль автоматического обновления агента PC-Guardian.
Проверяет наличие новой версии на сервере и скачивает обновления.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
import tempfile
import shutil
import subprocess
import time
import signal
import hashlib
from typing import Optional, Tuple, List, Dict
from pathlib import Path

from __version__ import __version__


class UpdateChecker:
    """Класс для проверки и установки обновлений агента"""

    def __init__(self, update_server_url: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Args:
            update_server_url: URL сервера обновлений (например, http://server:8000/updates)
            logger: Логгер для записи событий
        """
        self.update_server_url = update_server_url
        self.logger = logger or logging.getLogger(__name__)
        self.current_version = __version__
        self._agent_instance = None  # Ссылка на экземпляр агента для graceful shutdown

    def check_for_updates(self) -> Optional[Tuple[str, str, Optional[str]]]:
        """
        Проверяет наличие новой версии на сервере.
        
        Returns:
            Tuple (version, download_url, checksum) если есть обновление, иначе None
        """
        if not self.update_server_url:
            self.logger.debug("URL сервера обновлений не указан, проверка обновлений пропущена")
            return None

        try:
            # Получаем информацию о последней версии
            version_url = f"{self.update_server_url.rstrip('/')}/version.json"
            self.logger.info(f"Проверка обновлений на {version_url}")
            
            with urllib.request.urlopen(version_url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get('version')
                download_url = data.get('download_url')
                checksum = data.get('checksum')
                
                if not latest_version or not download_url:
                    self.logger.warning("Сервер обновлений вернул некорректные данные")
                    return None
                
                if self._compare_versions(self.current_version, latest_version) < 0:
                    self.logger.info(f"Найдена новая версия: {latest_version} (текущая: {self.current_version})")
                    return (latest_version, download_url, checksum)
                else:
                    self.logger.debug(f"Агент актуален (версия {self.current_version})")
                    return None
                    
        except urllib.error.URLError as e:
            self.logger.warning(f"Ошибка при проверке обновлений: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"Ошибка парсинга ответа сервера: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при проверке обновлений: {e}")
            return None

    def _calc_sha256(self, file_path: Path) -> str:
        """Вычисляет SHA256 для файла."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_checksum(self, file_path: Path, expected_checksum: Optional[str]) -> bool:
        """Проверяет контрольную сумму если она задана."""
        if not expected_checksum:
            return True
        try:
            actual = self._calc_sha256(file_path)
            if actual.lower() != expected_checksum.lower():
                self.logger.error(f"Контрольная сумма не совпала: ожидалось {expected_checksum}, получено {actual}")
                return False
            self.logger.info("Контрольная сумма обновления подтверждена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при проверке контрольной суммы: {e}")
            return False

    def download_update(self, download_url: str, target_path: Optional[str] = None, expected_checksum: Optional[str] = None) -> Optional[str]:
        """
        Скачивает обновление с сервера.
        
        Args:
            download_url: URL для скачивания exe файла
            target_path: Путь для сохранения файла (если None, используется временная директория)
            expected_checksum: Ожидаемая SHA256 для проверки целостности
            
        Returns:
            Путь к скачанному файлу или None в случае ошибки
        """
        try:
            self.logger.info(f"Скачивание обновления с {download_url}")
            
            if target_path is None:
                # Используем временную директорию
                temp_dir = tempfile.gettempdir()
                target_path = os.path.join(temp_dir, "PCGuardianAgent_update.exe")
            
            # Скачиваем файл
            urllib.request.urlretrieve(download_url, target_path)
            self.logger.info(f"Обновление скачано: {target_path}")

            # Проверяем контрольную сумму, если указана
            if expected_checksum:
                if not self._verify_checksum(Path(target_path), expected_checksum):
                    self.logger.error("Проверка контрольной суммы не пройдена, обновление отклонено")
                    try:
                        Path(target_path).unlink()
                    except Exception:
                        pass
                    return None

            return target_path
            
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании обновления: {e}")
            return None

    def install_update(self, update_file_path: str) -> bool:
        """
        Устанавливает обновление, заменяя текущий exe файлом обновления.
        
        Args:
            update_file_path: Путь к скачанному файлу обновления
            
        Returns:
            True если установка успешна, False в противном случае
        """
        try:
            # Определяем путь к текущему exe
            if getattr(sys, 'frozen', False):
                # Запущено из exe (PyInstaller)
                current_exe = sys.executable
            else:
                # Запущено из Python скрипта
                current_exe = sys.argv[0]
            
            current_exe_path = Path(current_exe).resolve()
            update_file_path = Path(update_file_path).resolve()
            
            if not update_file_path.exists():
                self.logger.error(f"Файл обновления не найден: {update_file_path}")
                return False
            
            # Создаём резервную копию текущего exe
            backup_path = current_exe_path.with_suffix('.exe.backup')
            if current_exe_path.exists():
                shutil.copy2(current_exe_path, backup_path)
                self.logger.info(f"Создана резервная копия: {backup_path}")
            
            # Заменяем текущий exe новым
            shutil.copy2(update_file_path, current_exe_path)
            self.logger.info(f"Обновление установлено: {current_exe_path}")
            
            # Удаляем временный файл
            try:
                update_file_path.unlink()
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при установке обновления: {e}")
            return False

    def update_if_available(self) -> bool:
        """
        Проверяет наличие обновлений и устанавливает их, если доступны.
        
        Returns:
            True если обновление было установлено, False в противном случае
        """
        update_info = self.check_for_updates()
        if not update_info:
            return False
        
        version, download_url, checksum = update_info
        self.logger.info(f"Начинается установка обновления до версии {version}")
        
        # Скачиваем обновление
        update_file = self.download_update(download_url, expected_checksum=checksum)
        if not update_file:
            return False
        
        # Устанавливаем обновление
        if self.install_update(update_file):
            self.logger.info(f"Обновление до версии {version} успешно установлено. Перезапустите агент.")
            return True
        else:
            return False
    
    def set_agent_instance(self, agent_instance):
        """Устанавливает ссылку на экземпляр агента для graceful shutdown"""
        self._agent_instance = agent_instance
    
    def _get_current_exe_path(self) -> Path:
        """Получает путь к текущему exe файлу"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve()
        else:
            return Path(sys.argv[0]).resolve()
    
    def _get_launch_args(self) -> List[str]:
        """Получает аргументы командной строки текущего процесса для передачи новому"""
        # Сохраняем все аргументы кроме имени скрипта
        return sys.argv[1:]
    
    def _launch_new_version(self, new_exe_path: Path, launch_args: List[str]) -> Optional[subprocess.Popen]:
        """
        Запускает новую версию агента с теми же параметрами.
        
        Args:
            new_exe_path: Путь к новому exe файлу
            launch_args: Аргументы командной строки для передачи новому процессу
            
        Returns:
            Popen объект нового процесса или None в случае ошибки
        """
        try:
            # Формируем команду запуска
            cmd = [str(new_exe_path)] + launch_args
            
            self.logger.info(f"Запуск новой версии: {' '.join(cmd)}")
            
            # Запускаем новый процесс в отдельном окне (не наследуем консоль)
            # CREATE_NEW_PROCESS_GROUP для Windows позволяет корректно завершить процесс
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                new_process = subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                new_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            # Даём процессу немного времени на запуск
            time.sleep(2)
            
            # Проверяем, что процесс всё ещё работает
            if new_process.poll() is None:
                self.logger.info(f"Новая версия успешно запущена (PID: {new_process.pid})")
                return new_process
            else:
                self.logger.error(f"Новая версия завершилась сразу после запуска (код возврата: {new_process.returncode})")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка при запуске новой версии: {e}")
            return None
    
    def _perform_graceful_shutdown(self):
        """Выполняет graceful shutdown текущего агента"""
        try:
            if self._agent_instance:
                self.logger.info("Выполняется graceful shutdown агента...")
                # Если мы в потоке consumer'а, не пытаемся ждать его join.
                self._agent_instance.stop()
            else:
                self.logger.warning("Экземпляр агента не установлен, выполняется принудительное завершение")
                # Если нет ссылки на агент, просто завершаем процесс
                sys.exit(0)
        except Exception as e:
            self.logger.error(f"Ошибка при graceful shutdown: {e}")
            sys.exit(1)
    
    def perform_seamless_update(self, download_url: str, version: str, checksum: Optional[str] = None) -> bool:
        """
        Выполняет незаметное обновление: скачивает новую версию, запускает её и завершает старую.
        
        Args:
            download_url: URL для скачивания нового exe
            version: Версия обновления
            checksum: Ожидаемая SHA256 (опционально)
            
        Returns:
            True если обновление успешно, False в противном случае
        """
        try:
            self.logger.info(f"Начинается незаметное обновление до версии {version}")
            
            # Определяем путь к текущему exe
            current_exe = self._get_current_exe_path()
            current_dir = current_exe.parent
            
            # Скачиваем обновление во временный файл в той же директории
            temp_exe_name = f"PCGuardianAgent_new_{int(time.time())}.exe"
            temp_exe_path = current_dir / temp_exe_name
            
            self.logger.info(f"Скачивание обновления в {temp_exe_path}")
            urllib.request.urlretrieve(download_url, str(temp_exe_path))

            # Проверяем контрольную сумму, если она указана
            if checksum:
                if not self._verify_checksum(temp_exe_path, checksum):
                    try:
                        temp_exe_path.unlink()
                    except Exception:
                        pass
                    return False
            
            # Проверяем, что файл скачался
            if not temp_exe_path.exists() or temp_exe_path.stat().st_size == 0:
                self.logger.error("Скачанный файл пуст или не существует")
                return False
            
            self.logger.info(f"Обновление скачано: {temp_exe_path.stat().st_size} байт")
            
            # Получаем аргументы запуска текущего процесса
            launch_args = self._get_launch_args()
            
            # Запускаем новую версию
            new_process = self._launch_new_version(temp_exe_path, launch_args)
            if not new_process:
                self.logger.error("Не удалось запустить новую версию")
                try:
                    temp_exe_path.unlink()
                except Exception:
                    pass
                return False
            
            # Даём новой версии время на инициализацию
            self.logger.info("Ожидание инициализации новой версии...")
            time.sleep(3)
            
            # Проверяем, что новый процесс всё ещё работает
            if new_process.poll() is not None:
                self.logger.error(f"Новая версия завершилась (код: {new_process.returncode})")
                return False
            
            self.logger.info("Новая версия успешно запущена, завершение старой версии...")
            
            # Выполняем graceful shutdown старого агента
            # Это вызовет sys.exit() в конце
            self._perform_graceful_shutdown()
            
            # Этот код не должен выполниться, но на всякий случай
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при незаметном обновлении: {e}")
            return False
    
    def handle_kafka_update_notification(self, notification: dict) -> bool:
        """
        Обрабатывает уведомление об обновлении из Kafka.
        
        Args:
            notification: Словарь с информацией об обновлении:
                - version: версия обновления
                - download_url: URL для скачивания exe файла
                - checksum: sha256 (опционально)
                
        Returns:
            True если обновление было установлено, False в противном случае
        """
        try:
            version = notification.get('version')
            download_url = notification.get('download_url')
            checksum = notification.get('checksum')
            
            if not version or not download_url:
                self.logger.warning("Уведомление об обновлении содержит некорректные данные")
                return False
            
            # Проверяем, действительно ли это новая версия
            if self._compare_versions(self.current_version, version) >= 0:
                self.logger.debug(f"Получено уведомление о версии {version}, но текущая версия {self.current_version} не ниже")
                return False
            
            self.logger.info(f"Получено уведомление об обновлении до версии {version} (текущая: {self.current_version})")
            
            # Выполняем незаметное обновление
            return self.perform_seamless_update(download_url, version, checksum)
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке уведомления об обновлении: {e}")
            return False

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """
        Сравнивает две версии в формате semver (например, "1.2.3").
        
        Returns:
            -1 если v1 < v2, 0 если v1 == v2, 1 если v1 > v2
        """
        def version_tuple(v: str):
            parts = v.split('.')
            return tuple(int(part) for part in parts)
        
        try:
            t1 = version_tuple(v1)
            t2 = version_tuple(v2)
            if t1 < t2:
                return -1
            elif t1 > t2:
                return 1
            else:
                return 0
        except (ValueError, AttributeError):
            # Если версии не в формате semver, сравниваем как строки
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0

