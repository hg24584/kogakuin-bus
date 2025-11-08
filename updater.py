import os
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import subprocess
import requests
import httpx
import json
import time
import os
import re
from datetime import datetime

url = "https://www.js.kogakuin.ac.jp/student/office/bus.html"
gemini_model = "gemini-2.5-flash"


def geminiOCR(doc):
    client = genai.Client()
    doc_data = httpx.get(doc).content

    prompt = 'このPDFデータは工学院大学附属中学校・高等学校のバス時刻表です。PDFの時刻表を解析し、「下校便の」みの時刻を添付のJSONの形式で日付ごとにまとめ、その日付内で行先ごとに分類してください。日付が範囲指定であれば一日ごとに書いてください。時刻は"hhmm"で:は不要です。コードブロック(```json など)は付けないでください。必ずJSONのみで返答してください。下校便がPDFに含まれていない場合はjsonを返さないでください。サンプルのJSONは以下の通りです。{"2025-10-01":{"JR八王子駅南口便":["1325②","1330","1455","1458京"],"京王八王子便":["1328","1458","1550"],"南大沢便":["1326京","1456京JR","1551京"],"拝島便":["1325","1330","1455","1458②","1600"]}}'
    print("now generating...")
    respons = client.models.generate_content(
        model=gemini_model,
        contents=[
            types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf"
            ),
            prompt
        ]
    )
    raw = respons.text.strip()
    match = re.search(r'\{[\s\S]*\}', raw)
    try:
        data_json = json.loads(match.group(0))
    except Exception as e:
        print(e)
        return None
    data = json.dumps(data_json, indent=1, ensure_ascii=False)
    print("generated")
    # print(data)
    time.sleep(5)
    return data_json

def getPdfUrl():
    get_attempt = 1
    PDF_list = []
    while True:
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if href.lower().endswith('.pdf'):
                    pdf_url = requests.compat.urljoin(url, href)
                    PDF_list.append(pdf_url)
            break
        except Exception as e:
            print(f"\nリクエスト失敗（試行回数：{get_attempt}）")
            print("error: ", e)
            get_attempt += 1

    print("\n以下のPDFを確認しました:")
    for link in PDF_list:
        print("> ", link)
    return PDF_list

def githubUpdate(merged_result):
    # try:
    #     json_data = json.dumps(merged_result, sort_keys=True, indent=4, ensure_ascii=False)
    #     repo = g.get_repo(repo_path)
    #     contents = repo.get_contents("timetable.json", ref="main")
    #     repo.update_file(
    #         path = contents.path,
    #         message = f"automatic update timetable.json {time.strftime('%Y-%m-%d %H:%M:%S')}",
    #         content = json_data,
    #         sha = contents.sha,
    #     )
    # except Exception as e:
    #     print("error: ", e)
    # finally:
    #     g.close()
    merged_result["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    json_data = json.dumps(merged_result, sort_keys=True, indent=4, ensure_ascii=False)
    with open("timetable.json", "w", encoding="utf-8") as f:
        f.write(json_data)
    print("complete")


def main():
    links = getPdfUrl()
    if not links:
        print("PDFが見つかりませんでした。")
        return
    merged_result = {}
    for link in links[1:]:
        attempts = 0
        while attempts < 3:
            results = []
            for _ in range(3):
                data = geminiOCR(link)
                if data is None:
                    break
                results.append(data)
                time.sleep(30)

            if len(results) < 3:
                print("OCRに失敗しました。60秒後に再試行します...")
                attempts += 1
                time.sleep(60)
                continue

            if results[0] == results[1] == results[2]:
                print(f"{link} のOCR結果が全て一致しました。")
                for day, routes in results[0].items():
                    merged_result.setdefault(day, {}).update(routes)
                break
            else:
                print("OCR結果が一致しませんでした。60秒後に再試行します...")
                attempts += 1
                time.sleep(60)
        else:
            print(f"{link} のOCR結果は最大試行回数でも一致しませんでした。次のPDFへ進みます。")

    print("操作が完了しました。結果は以下の通りです。")
    print(merged_result)
    githubUpdate(merged_result)


if __name__ == "__main__":
    main()
