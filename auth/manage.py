"""Trusted local provisioning. Run from the repository: python -m auth.manage."""

from __future__ import annotations

import argparse
import getpass
import sys

from .service import AuthError, AuthService, ROLES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Настройка учётных записей Career Quest на сервере.")
    parser.add_argument("--db", help="Путь к SQLite; иначе CAREER_QUEST_AUTH_DB или auth/.local/auth.sqlite3.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create-admin", help="Интерактивно создать первого администратора.")
    role_parser = subparsers.add_parser("set-role", help="Изменить роль зарегистрированного аккаунта и отозвать его сессии.")
    role_parser.add_argument("--email", required=True)
    role_parser.add_argument("--role", choices=sorted(ROLES), required=True)
    args = parser.parse_args(argv)
    try:
        service = AuthService(args.db)
        if args.command == "create-admin":
            name = input("Имя администратора: ")
            email = input("Электронная почта: ")
            password = getpass.getpass("Пароль (15–128 символов): ")
            confirmation = getpass.getpass("Повторите пароль: ")
            user = service.create_admin(name, email, password, confirmation)
            print(f"Администратор создан: {user['email']}.")
        else:
            user = service.assign_role(args.email, args.role)
            print(f"Роль аккаунта {user['email']}: {user['role']}. Активные сессии отозваны.")
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nОперация отменена.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
