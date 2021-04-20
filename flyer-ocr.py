import json
settings_json = open('settings.json', 'r', encoding='utf_8')
settings = json.load(settings_json)

# 公式サイトからpdfリンク一覧取得
def get_urls():
  import requests
  from bs4 import BeautifulSoup

  params = { settings['url_params_name']: settings['url_params_value'] }
  load_url = settings['url']
  html = requests.get(load_url, params=params)
  soup = BeautifulSoup(html.text, 'html.parser')

  flyer_list = soup.find_all('table')
  url_list = []
  for flyer in flyer_list:
    # 日付
    date = flyer.find('div', {'class': 'sale'}).find('a').get_text(strip=True).replace(' ', '').replace('（', '(').replace('）', ')')
    
    # PDF(表)
    omote_url = flyer.find('a', {'title': 'PDFオモテ'})['href']
    omote = {}
    omote['date'] = date
    omote['url'] = settings['url_stem'] + omote_url.replace('../', '')
    url_list.append(omote)

    # PDF(裏)
    if flyer.find('a', {'title': 'PDFウラ'}):
      ura_url = flyer.find('a', {'title': 'PDFウラ'})['href'] 
      ura = {}
      ura['date'] = date
      ura['url'] = settings['url_stem'] + ura_url.replace('../', '')
      url_list.append(ura)

  return url_list

# 未解析のチラシURLを取得
def get_new_urls(url_list):
  # urls.txt読込
  old_urls = []
  with open('urls.txt', 'r') as f:
    old_urls = f.read().splitlines()

  new_urls = []
  urls_text = []
  count = 0
  for url_info in url_list:
    urls_text.append(url_info['url'] + '\n')

    if url_info['url'] not in old_urls:
      # 新規
      url_info['number'] = count
      new_urls.append(url_info)
      count += 1
  
  # urls.txt書込
  f = open('urls.txt', 'w')
  f.writelines(urls_text)
  f.close()

  return new_urls

# 未解析のpdfをDL
def dl_pdfs(new_url_list):
  import urllib.request
  import time

  pdf_list = []
  for url_info in new_url_list:
    # 表
    file_name = f'pdf/{url_info["number"]}.pdf'
    urllib.request.urlretrieve(url_info['url'], file_name)
    url_info['pdf_path'] = file_name

    time.sleep(2)

    pdf_list.append(url_info)

  return pdf_list

# PDFをJPGに変換
def pdf_to_jpeg(path):
  import os
  from pathlib import Path
  from pdf2image import convert_from_path

  # poppler/binを環境変数PATHに追加する
  poppler_dir = Path(__file__).parent.absolute() / 'lib/poppler/bin'
  os.environ['PATH'] += os.pathsep + str(poppler_dir)

  image_paths = []

  pdf_path = Path(path)
  # PDF -> Image に変換（150dpi）
  pages = convert_from_path(str(pdf_path), 150)

  # 画像ファイルを１ページずつ保存
  image_dir = Path('./jpg')
  for i, page in enumerate(pages):
    file_name = pdf_path.stem + '_{:02d}'.format(i + 1) + '.jpeg'
    image_path = image_dir / file_name
    # JPEGで保存
    page.save(str(image_path), 'JPEG')
    image_paths.append(image_path)

  return image_paths

# 複数チラシをJPGに変換
def pdfs_to_jpeg(pdf_list):
  jpg_list = []
  for pdf_info in pdf_list:
    jpg_info = pdf_info
    # 表
    omote_image_paths = pdf_to_jpeg(pdf_info['pdf_path'])
    jpg_info['image_paths'] = omote_image_paths

    jpg_list.append(jpg_info)

  return jpg_list

# OCR
def detect_text(image_paths):
  from google.cloud import vision
  import io
  client = vision.ImageAnnotatorClient()

  all_text = ''

  for image_path in image_paths:
    with io.open(image_path, 'rb') as image_file:
      content = image_file.read()

    image = vision.Image(content=content)
    
    # pylint: disable=no-member
    response = client.text_detection(image=image)
    texts = response.text_annotations

    for text in texts:
      all_text += str(text.description)

    if response.error.message:
      raise Exception(
        '{}\nFor more info on error messages, check: '
        'https://cloud.google.com/apis/design/errors'.format(
          response.error.message))

  return all_text

# キーワード検索
def search_words(all_text):
  hitwords = []
  for keyword in settings["keywords"]:
    if keyword in all_text:
      hitwords.append(keyword)

  return hitwords

# キーワードに引っかかったチラシ取得
def get_target_flyers(jpg_list):
  result = []
  for jpg_info in jpg_list:
    all_text = detect_text(jpg_info['image_paths'])
    hitwords = search_words(all_text)

    if len(hitwords) != 0:
      hit = jpg_info
      hit['hitwords'] = hitwords
      result.append(hit)

  return result

# Slack通知
def slack_notice(results):
  import slackweb
  slack = slackweb.Slack(url=settings['slack_webhook_url'])
  for result in results:
    text = f'{result["date"]} チラシ掲載商品：{",".join(result["hitwords"])}\n<{result["url"]}|チラシを見る>'
    slack.notify(text=text)

### FlyerOCR ###
import shutil
import os
os.makedirs('pdf/', exist_ok=True)
os.makedirs('jpg/', exist_ok=True)

url_list = get_urls()
new_url_list = get_new_urls(url_list)
pdf_list = dl_pdfs(new_url_list)
jpg_list = pdfs_to_jpeg(pdf_list)
results = get_target_flyers(jpg_list)
slack_notice(results)

shutil.rmtree('pdf/')
shutil.rmtree('jpg/')
