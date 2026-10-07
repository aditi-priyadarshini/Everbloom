from playwright.sync_api import sync_playwright
import json
import argparse
parser=argparse.ArgumentParser()
parser.add_argument("--base-url",default="http://127.0.0.1:5000")
parser.add_argument("--chromium",default="/usr/bin/chromium")
args=parser.parse_args()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
 results=[]
 for width in [360,390,768,1024,1440]:
  page=browser.new_page(viewport={'width':width,'height':1000})
  for route in ['/','/shop','/auth/login','/custom-order','/cart']:
   response=page.goto(args.base_url+route,wait_until='domcontentloaded')
   overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
   results.append({'width':width,'route':route,'status':response.status,'overflow':overflow})
  if width==390:
   page.goto(args.base_url+'/')
   page.locator('#hamburger').click()
   assert page.locator('#hamburger').get_attribute('aria-expanded')=='true'
   page.keyboard.press('Escape')
   assert page.locator('#hamburger').get_attribute('aria-expanded')=='false'
  page.close()
 browser.close()
 print(json.dumps(results))
 assert not any(r['overflow'] or r['status']!=200 for r in results)
