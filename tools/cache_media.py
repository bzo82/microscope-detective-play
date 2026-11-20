#!/usr/bin/env python3
"""Assemble a license-checked photo set from exact Wikimedia Commons file titles.
Fails closed: images lacking an allowed Wikimedia license are never bundled.
No random image search is used.
"""
import concurrent.futures, html, io, json, logging, re, time
from pathlib import Path
from urllib.parse import quote
import requests
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"assets"
ASSETS.mkdir(exist_ok=True)
COMMONS="https://commons.wikimedia.org/w/api.php"
WIKIPEDIA="https://en.wikipedia.org/w/api.php"
HEADERS={"User-Agent":"MicroscopeDetective/1.0 (educational visual quiz; https://github.com/bzo82/microscope-detective-play)"}
LICENSE=re.compile(r"^(?:CC0|CC BY(?:-SA)?(?:-| |$)|CC-BY|CC-BY-SA|PD-|Public domain)",re.I)
logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
def query(url,**kwargs):
  kwargs.update(action="query",format="json",formatversion=2)
  for attempt in range(3):
    try:
      r=requests.get(url,params=kwargs,headers=HEADERS,timeout=20)
      r.raise_for_status()
      return r.json()
    except Exception as exc:
      logging.warning("API %s failed: %s",kwargs.get("titles"),str(exc)[:80])
      time.sleep(attempt+1)
  return {}
def text(x):
  return html.unescape(re.sub(r"<[^>]*>","",x or "")).strip()[:170]
def commons(filename):
  if not filename:return None
  d=query(COMMONS,prop="imageinfo",iiprop="url|extmetadata",iiurlwidth=1100,titles="File:"+filename)
  pages=d.get("query",{}).get("pages",[])
  if not pages or "imageinfo" not in pages[0]:return None
  obj=pages[0]["imageinfo"][0]
  md=obj.get("extmetadata",{})
  lic=text(md.get("LicenseShortName",{}).get("value",""))
  author=text(md.get("Artist",{}).get("value",""))
  if not LICENSE.match(lic) or not author:return None
  return {"url":obj.get("thumburl") or obj.get("url"),"author":author,"license":lic,"source":"https://commons.wikimedia.org/wiki/File:"+quote(filename.replace(" ","_"),safe=""),"licenseUrl":md.get("LicenseUrl",{}).get("value","")}
def wiki(article):
  if not article:return None
  d=query(WIKIPEDIA,prop="pageimages",piprop="name",titles=article,redirects=1)
  pages=d.get("query",{}).get("pages",[])
  return commons(pages[0].get("pageimage")) if pages else None
def fetch(item):
  q,kind=item
  try:
    m=commons(q.get(kind)) if q.get(kind) else (wiki(q.get("macroArticle")) if kind=="macro" else None)
    if not m:return q["id"],kind,None
    url=m.pop("url")
    if not url or not url.startswith("https://") or "wikimedia.org" not in url:return q["id"],kind,None
    response=requests.get(url,headers=HEADERS,timeout=30)
    response.raise_for_status()
    if len(response.content)>14000000:return q["id"],kind,None
    im=Image.open(io.BytesIO(response.content))
    im=ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((1100,900),Image.Resampling.LANCZOS)
    if im.width<150 or im.height<120:return q["id"],kind,None
    path=ASSETS/(q["id"]+"-"+kind+".jpg")
    im.save(path,"JPEG",quality=82,progressive=True,optimize=True)
    m["path"]="./assets/"+path.name
    m["note"]="Resized JPEG of the attributed original"
    return q["id"],kind,m
  except Exception as exc:
    logging.warning("skip %s/%s: %s",q["id"],kind,str(exc)[:100])
    return q["id"],kind,None

def main():
  questions=json.loads((ROOT/"questions.json").read_text(encoding="utf8"))
  index={q["id"]:{} for q in questions}
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for id,kind,media in pool.map(fetch,[(q,k) for q in questions for k in ("micro","macro")]):
      if media:index[id][kind]=media
  (ASSETS/"manifest.json").write_text(json.dumps(index,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
  summary={k:sum(k in record for record in index.values()) for k in ("micro","macro")}
  (ASSETS/"report.json").write_text(json.dumps(summary,indent=2)+"\n")
  logging.info("Media results: %s",summary)
if __name__=="__main__":main()
