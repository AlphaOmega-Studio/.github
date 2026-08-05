import re
from datetime import datetime
with open("LICENSE.md","r+") as f:
    c=f.read()
    y=sorted(map(int,re.findall(r'\b20\d{2}\b',c)))
    if y:
        n=f"{min(y)}-{datetime.now().year}" if datetime.now().year != min(y) else str(min(y))
        f.seek(0)
        f.write(re.sub(r'\b20\d{2}\b',n,c))
        f.truncate()
