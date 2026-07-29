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
            "description": repo.description or "—",
            "language": repo.language or "—",
            "license": repo.license.name if repo.license else "—",
            "created_at": repo.created_at.strftime("%d-%m-%Y"),
            "updated_at": repo.updated_at.strftime("%d-%m-%Y"),
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "size_mb": round(repo.size / 1024, 1) if repo.size else 0,
        }
        try:
            repo.get_readme()
            data["has_readme"] = True
        except GithubException:
            data["has_readme"] = False
        try:
            releases = repo.get_releases()
            data["release_count"] = releases.totalCount
            total_downloads = 0
            for rel in releases:
                for asset in rel.get_assets():
                    total_downloads += asset.download_count
            data["total_downloads"] = total_downloads
        except GithubException:
            data["release_count"] = 0
            data["total_downloads"] = 0
        result.append(data)
    return result
def generate_table(repos_data):
    if not repos_data:
        return "Нет репозиториев"
    headers = [
        "Проект Project", "Описание Description", "Язык Language", "Лицензия Licence",
        "Создан Created", "Обновлён Updated", "⭐", "🍴",
        "Размер (МБ) Size (MB)", "README", "Релизов Releases", "Скачиваний Downloads"
    ]
    rows = []
    for r in repos_data:
        desc = r['description'][:40] + "…" if len(r['description']) > 40 else r['description']
        rows.append([
            f"[{r['name']}](https://github.com/{r['full_name']})",
            desc,
            r['language'],
            r['license'],
            r['created_at'],
            r['updated_at'],
            str(r['stars']),
            str(r['forks']),
            str(r['size_mb']),
            "✅" if r['has_readme'] else "❌",
            str(r['release_count']),
            str(r['total_downloads']),
        ])
    table = "| " + " | ".join(headers) + " |\n"
    table += "| " + " | ".join([":---:"] * len(headers)) + " |\n"
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
    timestamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")
    full_table = f"*Данные актуальны на {timestamp}*\n\n" + table
    update_readme(README_PATH, full_table)
if __name__ == "__main__":
    main()
