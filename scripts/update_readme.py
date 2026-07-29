import os,re
from datetime import datetime,timezone
from github import Github,Auth,GithubException
def gd(g,o):
    d=[]
    for r in g.get_organization(o).get_repos():
        if r.name==".github": continue
        x={"name":r.name,"full_name":r.full_name,"description":r.description or"—","language":r.language or"—","license":r.license.name if r.license else"—","created_at":r.created_at.strftime("%d-%m-%Y"),"updated_at":r.updated_at.strftime("%d-%m-%Y"),"stars":r.stargazers_count,"forks":r.forks_count,"size_mb":round(r.size/1024,1) if r.size else 0}
        try: r.get_readme(); x["has_readme"]=1
        except: x["has_readme"]=0
        try:
            s=0;c=0
            for l in r.get_releases():
                for a in l.get_assets(): s+=a.download_count
                c+=1
            x["release_count"]=c; x["total_downloads"]=s
        except: x["release_count"]=0; x["total_downloads"]=0
        d.append(x)
    return d
def gt(d):
    if not d: return "Нет репозиториев"
    h=["Проект Project","Описание Description","Язык Language","Лицензия Licence","Создан Created","Обновлён Updated","⭐","🍴","Размер (МБ) Size (MB)","README","Релизов Releases","Скачиваний Downloads"]
    b="| "+" | ".join(h)+" |\n| "+" | ".join([":---:"]*len(h))+" |\n"
    for r in d:
        p=r['description'][:40]+"…" if len(r['description'])>40 else r['description']
        b+="| "+" | ".join([f"[{r['name']}](https://github.com/{r['full_name']})",p,r['language'],r['license'],r['created_at'],r['updated_at'],str(r['stars']),str(r['forks']),str(r['size_mb']),"✅" if r['has_readme'] else"❌",str(r['release_count']),str(r['total_downloads'])])+" |\n"
    return b
def u(p,t):
    with open(p,"r",encoding="utf-8") as f: c=f.read()
    with open(p,"w",encoding="utf-8") as f: f.write(re.sub(r'(<!-- s -->\n).*?(\n<!-- e -->)',r'\1'+t+r'\2',c,flags=re.DOTALL))
if __name__=="__main__":
    t=os.getenv("GITHUB_TOKEN"); o=os.getenv("ORGANIZATION")
    if not t or not o: exit(1)
    g=Github(auth=Auth.Token(t))
    u("profile/README.md",f"*Данные актуальны на / Data updated on {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M UTC')}*\n\n"+gt(gd(g,o)))
