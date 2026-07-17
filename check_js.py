import urllib.request
import re
try:
    html = urllib.request.urlopen('https://travex-ai.vercel.app/').read().decode('utf-8')
    match = re.search(r'src=\"(/assets/[^\"]+\.js)\"', html)
    if match:
        js_url = 'https://travex-ai.vercel.app' + match.group(1)
        print("JS URL:", js_url)
        js_content = urllib.request.urlopen(js_url).read().decode('utf-8')
        if 'https://travex-lilac.vercel.app' in js_content:
            print("BACKEND URL FOUND IN VITE BUNDLE!")
        else:
            print("BACKEND URL NOT FOUND. ENV VAR ISSUE!")
    else:
        print("No JS found in HTML")
except Exception as e:
    print("Error:", e)
