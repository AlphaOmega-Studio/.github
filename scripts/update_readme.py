#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime

from github import Github, Auth, GithubException
from github.GithubException import RateLimitExceededException

TOKEN = os.getenv("GITHUB_TOKEN")
ORG_NAME = os.getenv("ORGANIZATION")
README_PATH = "profile/README.md"


def get_repos_data(g, org_name):
    org = g.get_organization(org_name)
    repos = org.get_repos()
    repos_data = []

    for repo in repos:
        if repo.name == ".github":
            continue

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
            "size": repo.size,
            "default_branch": repo.default_branch,
            "private": repo.private,
            "archived": repo.archived,
            "fork": repo.fork,
        }

        try:
            # 1. Статистика коммитов (последние 52 недели)
            stats = repo.get_stats_commit_activity()
            if stats:
                total_weekly = sum(week.total for week in stats[-1:])
                data["weekly_commits"] = total_weekly
            else:
                data["weekly_commits"] = 0

            # 2. Топ-5 контрибьюторов
            contributors = repo.get_contributors()
            top = []
            for i, cont in enumerate(contributors[:5]):
                top.append(f"{cont.login} ({cont.contributions})")
            data["top_contributors"] = ", ".join(top) if top else "—"

            # 3. Профиль сообщества (с защитой от отсутствия метода)
            try:
                community = repo.get_community_profile()
            except (GithubException, AttributeError):
                community = None

            if community:
                data["health_percentage"] = community.health_percentage
                files = community.files
                data["has_readme"] = files.readme is not None
                data["has_contributing"] = files.contributing is not None
                data["has_code_of_conduct"] = files.code_of_conduct is not None
            else:
                data["health_percentage"] = 0
                data["has_readme"] = False
                data["has_contributing"] = False
                data["has_code_of_conduct"] = False

            # 4. Трафик (просмотры и клоны за 14 дней)
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

            # 5. Статистика Actions
            try:
                runs = repo.get_workflow_runs()
                total = runs.totalCount
                success = sum(1 for r in runs[:100] if r.conclusion == "success")
                data["actions_total"] = total
                data["actions_success_rate"] = f"{(success / (total or 1) * 100):.0f}%"
            except GithubException:
                data["actions_total"] = 0
                data["actions_success_rate"] = "—"

            # 6. Релизы и скачивания (безопасный перебор без среза)
            releases = repo.get_releases()
            data["release_count"] = releases.totalCount
            downloads = 0
            rel_count = 0
            for rel in releases:
                if rel_count >= 5:
                    break
                for asset in rel.get_assets():
                    downloads += asset.download_count
                rel_count += 1
            data["total_downloads"] = downloads

            # 7. Открытые PR и Issues
            data["open_prs"] = repo.get_pulls(state="open").totalCount
            all_open = repo.get_issues(state="open").totalCount
            data["open_issues"] = all_open - data["open_prs"]

        except (GithubException, RateLimitExceededException, AttributeError) as e:
            # Заполняем пропуски, чтобы не потерять репозиторий
            defaults = {
                "weekly_commits": "—",
                "top_contributors": "—",
                "health_percentage": "—",
                "has_readme": "—",
                "has_contributing": "—",
                "has_code_of_conduct": "—",
                "views_count": "—",
                "unique_visitors": "—",
                "clones_count": "—",
                "unique_cloners": "—",
                "actions_total": "—",
                "actions_success_rate": "—",
                "release_count": "—",
                "total_downloads": "—",
                "open_prs": "—",
                "open_issues": "—",
            }
            for key, value in defaults.items():
                data.setdefault(key, value)
            continue

        repos_data.append(data)

    return repos_data


def generate_table(repos_data):
    if not repos_data:
        return "Нет доступных репозиториев."

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

    rows = []
    for r in repos_data:
        desc = r['description'][:40] + "…" if len(r['description']) > 40 else r['description']
        top = r['top_contributors'][:30] + "…" if len(r['top_contributors']) > 30 else r['top_contributors']

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

    table = "| " + " | ".join(headers) + " |\n"
    table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in rows:
        table += "| " + " | ".join(row) + " |\n"
    return table


def update_readme(readme_path, table):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'(<!-- REPO_LIST:START -->\n).*?(\n<!-- REPO_LIST:END -->)'
    replacement = r'\1' + table + r'\2'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if not TOKEN or not ORG_NAME:
        print("Missing GITHUB_TOKEN or ORGANIZATION environment variables")
        exit(1)

    auth = Auth.Token(TOKEN)
    g = Github(auth=auth)

    repos_data = get_repos_data(g, ORG_NAME)
    table = generate_table(repos_data)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    full_table = f"*Данные актуальны на {timestamp}*\n\n" + table

    update_readme(README_PATH, full_table)


if __name__ == "__main__":
    main()
