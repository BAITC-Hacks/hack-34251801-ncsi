"""Trusted local provisioning. Run from the repository: python -m auth.manage."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from .service import AuthError, AuthService, ROLES
from storage.config import configure_storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Настройка учётных записей Career Quest на сервере.")
    parser.add_argument("--db", help="Путь к SQLite; иначе путь из локальных настроек хранилища.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create-admin", help="Интерактивно создать первого администратора.")
    subparsers.add_parser('seed-demo', help='Создать 4 демонстрационных аккаунта с общим публичным паролем; существующие аккаунты не изменяются.')
    role_parser = subparsers.add_parser("set-role", help="Изменить роль зарегистрированного аккаунта и отозвать его сессии.")
    role_parser.add_argument("--email", required=True)
    role_parser.add_argument("--role", choices=sorted(ROLES), required=True)
    args = parser.parse_args(argv)
    try:
        configure_storage()
        service = AuthService(args.db)
        if args.command == "create-admin":
            name = input("Имя администратора: ")
            email = input("Электронная почта: ")
            password = getpass.getpass("Пароль (15–128 символов): ")
            confirmation = getpass.getpass("Повторите пароль: ")
            user = service.create_admin(name, email, password, confirmation)
            print(f"Администратор создан: {user['email']}.")
        elif args.command == 'seed-demo':
            from .demo_seed import DEMO_PASSWORD, seed_demo_accounts
            from core.api import load_dataset
            from storage.config import ROOT
            from storage.dataset import DatasetStore
            data_dir = Path(os.environ.get('CAREER_QUEST_DATA_DIR') or ROOT / 'case/case_1/career_quest_dataset')
            if not data_dir.is_absolute():
                data_dir = ROOT / data_dir
            dataset, _ = DatasetStore().load_or_initialize(lambda: load_dataset(str(data_dir)))
            result = seed_demo_accounts(service, dataset['employees'])
            print(f"Создано аккаунтов: {len(result['created'])}; ранее созданных: {len(result['existing'])}.")
            for user in result['created']:
                print(f"{user['email']} | {user['role']} | {user['employee_id'] or '—'}")
            if result['created']:
                print(f'Общий пароль новых демоаккаунтов: {DEMO_PASSWORD}')
            if result['existing']:
                print('Существующие демоаккаунты, их пароли, роли и привязки сохранены без изменений.')
            print('Демоаккаунты предназначены для показа на тестовых данных. Основное приложение запускается с обычной проверкой пароля и роли.')
        else:
            user = service.assign_role(args.email, args.role)
            print(f"Роль аккаунта {user['email']}: {user['role']}. Активные сессии отозваны.")
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nОперация отменена.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
