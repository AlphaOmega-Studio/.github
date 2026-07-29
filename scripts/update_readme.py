import os
import re
from datetime import datetime, timezone

from github import Github, Auth, GithubException

TOKEN = os.getenv("GITHUB_TOKEN")
ORG_NAME = os.getenv("ORGANIZATION")
README_PATH = "profile/README.md"


def get_repos_data(g, org_name):
    org = g.get_organization(org_name)
    repos = org.get_repos()
    result = []

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
            stats = repo.get_stats_commit_activity()
            data["weekly_commits"] = sum(w.total for w in stats[-1:]) if stats else 0

            contributors = repo.get_contributors()
            top = []
            for i, c in enumerate(contributors[:5]):
                top.append(f"{c.login} ({c.contributions})")
            data["top_contributors"] = ", ".join(top) if top else "—"

            try:
                community = repo.get_community_profile()
            except (GithubException, AttributeError):
                community = None

            if community:
                data["health_percentage"] = community.health_percentage
                f = community.files
                data["has_readme"] = f.readme is not None
                data["has_contributing"] = f.contributing is not None
                data["has_code_of_conduct"] = f.code_of_conduct is not None
            else:
                data["health_percentage"] = 0
                data["has_readme"] = False
                data["has_contributing"] = False
                data["has_code_of_conduct"] = False

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

            try:
                runs = repo.get_workflow_runs()
                total = runs.totalCount
                success = sum(1 for r in runs[:100] if r.conclusion == "success")
                data["actions_total"] = total
                data["actions_success_rate"] = f"{(success / (total or 1) * 100):.0f}%"
            except GithubException:
                data["actions_total"] = 0
                data["actions_success_rate"] = "—"

            releases = repo.get_releases()
            data["release_count"] = releases.totalCount
            downloads = 0
            count = 0
            for rel in releases:
                if count >= 5:
                    break
                for asset in rel.get_assets():
                    downloads += asset.download_count
                count += 1
            data["total_downloads"] = downloads

            data["open_prs"] = repo.get_pulls(state="open").totalCount
            all_open = repo.get_issues(state="open").totalCount
            data["open_issues"] = all_open - data["open_prs"]

        except (GithubException, AttributeError):
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
            for k, v in defaults.items():
                data.setdefault(k, v)
            continue

        result.append(data)

    return result


def generate_table(repos_data):
    if not repos_data:
        return "Нет репозиториев"

    headers = [
        "Проект", "Описание", "Язык", "Лицензия",
        "Создан", "Обновлён", "Пуш",
        "⭐", "🍴", "👀", "🐛",
        "Коммитов (7д)", "Топ контрибьюторы",
        "Здоровье %", "README", "CONTRIBUTING", "CoC",
        "Просмотры (14д)", "Уник. посетители",
        "Клоны (14д)", "Уник. клоны",
        "Actions (всего)", "Успешность",
        "Релизов", "Скачиваний",
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


def update_readme(path, table):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'(<!-- REPO_LIST_START -->\n).*?(\n<!-- REPO_LIST_END -->)'
    replacement = r'\1' + table + r'\2'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if not TOKEN or not ORG_NAME:
        print("Missing GITHUB_TOKEN or ORGANIZATION")
        exit(1)

    auth = Auth.Token(TOKEN)
    g = Github(auth=auth)

    repos_data = get_repos_data(g, ORG_NAME)
    table = generate_table(repos_data)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    full_table = f"*Данные актуальны на {timestamp}*\n\n" + table

    update_readme(README_PATH, full_table)


if __name__ == "__main__":
    main()
