#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime

from github import Github, Auth, GithubException
from github.GithubException import RateLimitExceededException

# Переменные окружения
TOKEN = os.getenv("GITHUB_TOKEN")
ORG_NAME = os.getenv("ORGANIZATION")
README_PATH = "profile/README.md"   # путь к README организации


def get_repos_data(g, org_name):
    """
    Собирает все данные по каждому репозиторию организации.
    Возвращает список словарей с полной информацией.
    """
    org = g.get_organization(org_name)
    repos = org.get_repos()

    repos_data = []
    for repo in repos:
        # Пропускаем репозиторий .github
        if repo.name == ".github":
            continue

        # Базовые метаданные
        data = {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description or "",
            "language": repo.language or "—",
            "license": repo.license.name if repo.license else "—",
            "created_at": repo.created_at.strftime("%Y-%m-%d"),
            "updated_at": repo.updated_at.strftime("%Y-%m-%d"),
            "pushed_at": repo.pushed_at.strftime("%Y-%m-%d"),
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "watchers": repo.watchers_count,
            "open_issues": repo.open_issues_count,
            "size": repo.size,  # КБ
            "default_branch": repo.default_branch,
            "private": repo.private,
            "archived": repo.archived,
            "fork": repo.fork,
        }

        # Дополнительная информация (требует отдельных запросов)
        try:
            # 1. Статистика коммитов за последние 52 недели
            commits_stats = repo.get_stats_commit_activity()
            if commits_stats:
                # Суммируем коммиты за последние 7 дней (последний элемент списка)
                total_weekly_commits = sum(week.total for week in commits_stats[-1:])
                data["weekly_commits"] = total_weekly_commits
            else:
                data["weekly_commits"] = 0

            # 2. Топ-5 контрибьюторов (по количеству коммитов)
            contributors = repo.get_contributors()
            top_contributors = []
            for i, cont in enumerate(contributors[:5]):
                top_contributors.append(f"{cont.login} ({cont.contributions})")
            data["top_contributors"] = ", ".join(top_contributors) if top_contributors else "—"

            # 3. Здоровье сообщества (community profile)
            community = repo.get_community_profile()
            if community:
                data["health_percentage"] = community.health_percentage
                # Наличие важных файлов
                files = community.files
                data["has_readme"] = files.readme is not None
                data["has_contributing"] = files.contributing is not None
                data["has_code_of_conduct"] = files.code_of_conduct is not None
            else:
                data["health_percentage"] = 0
                data["has_readme"] = False
                data["has_contributing"] = False
                data["has_code_of_conduct"] = False

            # 4. Трафик (просмотры и клоны за последние 14 дней)
            try:
                views = repo.get_views_traffic()
                data["views_count"] = views["count"] if views else 0
                data["unique_visitors"] = views["uniques"] if views else 0
            except GithubException:
                data["views_count"] = 0
                data["unique_visitors"] = 0

            try:
                clones = repo.get_clones_traffic()
                data["clones_count"] = clones["count"] if clones else 0
                data["unique_cloners"] = clones["uniques"] if clones else 0
            except GithubException:
                data["clones_count"] = 0
                data["unique_cloners"] = 0

            # 5. Статистика Actions (последние 100 запусков)
            try:
                actions_runs = repo.get_workflow_runs()
                total_runs = actions_runs.totalCount
                successful = sum(1 for run in actions_runs[:100] if run.conclusion == "success")
                data["actions_total"] = total_runs
                data["actions_success_rate"] = f"{(successful / (total_runs or 1) * 100):.0f}%"
            except GithubException:
                data["actions_total"] = 0
                data["actions_success_rate"] = "—"

            # 6. Количество релизов и общие скачивания (ограничим 5 релизами)
            releases = repo.get_releases()
            data["release_count"] = releases.totalCount
            total_downloads = 0
            for rel in releases[:5]:
                for asset in rel.get_assets():
                    total_downloads += asset.download_count
            data["total_downloads"] = total_downloads

            # 7. Количество открытых PR и Issues
            data["open_prs"] = repo.get_pulls(state="open").totalCount
            # get_issues возвращает и PR, и Issues, поэтому вычитаем PR
            all_open = repo.get_issues(state="open").totalCount
            data["open_issues"] = all_open - data["open_prs"]

        except (GithubException, RateLimitExceededException) as e:
            # Если какие-то данные недоступны (нет прав или 404), заполняем прочерками
            data.setdefault("weekly_commits", "—")
            data.setdefault("top_contributors", "—")
            data.setdefault("health_percentage", "—")
            data.setdefault("has_readme", "—")
            data.setdefault("has_contributing", "—")
            data.setdefault("has_code_of_conduct", "—")
            data.setdefault("views_count", "—")
            data.setdefault("unique_visitors", "—")
            data.setdefault("clones_count", "—")
            data.setdefault("unique_cloners", "—")
            data.setdefault("actions_total", "—")
            data.setdefault("actions_success_rate", "—")
            data.setdefault("release_count", "—")
            data.setdefault("total_downloads", "—")
            data.setdefault("open_prs", "—")
            data.setdefault("open_issues", "—")
            # Не прерываем сбор для остальных репозиториев
            continue

        repos_data.append(data)

    return repos_data


def generate_table(repos_data):
    """
    Генерирует Markdown-таблицу со всеми собранными данными.
    """
    if not repos_data:
        return "Нет доступных репозиториев."

    # Заголовки таблицы
    headers = [
        "Проект", "Описание", "Язык", "Лицензия",
        "Создан", "Обновлён", "Пуш",
        "⭐", "🍴", "👀", "🐛",
        "Коммитов (за 7д)", "Топ контрибьюторы",
        "Здоровье %", "README", "CONTRIBUTING", "CoC",
        "Просмотры (14д)", "Уник. посетители",
        "Клоны (14д)", "Уник. клоны",
        "Actions (всего)", "Успешность Actions",
        "Релизов", "Скачиваний (всего)",
        "Открытых PR", "Открытых Issues"
    ]

    # Строки
    rows = []
    for r in repos_data:
        # Ограничим длину описания и контрибьюторов для читаемости
        desc = r['description']
        if len(desc) > 40:
            desc = desc[:40] + "…"
        top = r['top_contributors']
        if len(top) > 30:
            top = top[:30] + "…"

        rows.append([
            f"[{r['name']}](https://github.com/{r['full_name']})",
            desc,
            r['language'],
            r['license'],
            r['created_at'],
            r['updated_at'],
            r['pushed_at'],
            str(r['stars']),
            str(r['forks']),
            str(r['watchers']),
            str(r['open_issues']),
            str(r['weekly_commits']),
            top,
            str(r['health_percentage']),
            "✅" if r['has_readme'] else "❌",
            "✅" if r['has_contributing'] else "❌",
            "✅" if r['has_code_of_conduct'] else "❌",
            str(r['views_count']),
            str(r['unique_visitors']),
            str(r['clones_count']),
            str(r['unique_cloners']),
            str(r['actions_total']),
            r['actions_success_rate'],
            str(r['release_count']),
            str(r['total_downloads']),
            str(r['open_prs']),
            str(r['open_issues']),
        ])

    # Построение таблицы
    table = "| " + " | ".join(headers) + " |\n"
    table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in rows:
        table += "| " + " | ".join(row) + " |\n"

    return table


def update_readme(readme_path, table):
    """
    Обновляет README.md, заменяя содержимое между маркерами.
    """
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Регулярка для поиска между маркерами
    pattern = r'(<!-- REPO_LIST_START -->\n).*?(\n<!-- REPO_LIST_END -->)'
    replacement = r'\1' + table + r'\2'

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if not TOKEN or not ORG_NAME:
        print("Missing GITHUB_TOKEN or ORGANIZATION environment variables")
        exit(1)

    # Современный способ авторизации
    auth = Auth.Token(TOKEN)
    g = Github(auth=auth)

    repos_data = get_repos_data(g, ORG_NAME)

    # Генерация таблицы с полной информацией
    table = generate_table(repos_data)

    # Добавляем временную метку (дата последнего обновления)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    full_table = f"*Данные актуальны на {timestamp}*\n\n" + table

    update_readme(README_PATH, full_table)


if __name__ == "__main__":
    main()
