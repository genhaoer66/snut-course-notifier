"""Local-only synthetic preview with real CDP viewport emulation."""
import base64
import functools
import http.server
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import unquote
import websocket

ROOT = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        resolved = (ROOT / unquote(path).lstrip('/')).resolve()
        if not (resolved == ROOT / 'design/ui-preview.html' or resolved.parent == ROOT / 'web'):
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
profile = tempfile.TemporaryDirectory(prefix='t06-edge-', dir=str(ROOT / 'design'))
process = subprocess.Popen([
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '--headless=new', '--disable-gpu', '--in-process-gpu', '--no-sandbox', '--disable-extensions', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--remote-debugging-port=0', '--remote-allow-origins=*',
    '--user-data-dir=' + profile.name, 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=open(ROOT / 'design/t06-edge.log', 'w'), creationflags=subprocess.CREATE_NO_WINDOW)
results = []
try:
    portfile = Path(profile.name) / 'DevToolsActivePort'
    for _ in range(100):
        if portfile.exists():
            break
        time.sleep(.1)
    port = portfile.read_text().splitlines()[0]
    tabs = json.load(urllib.request.urlopen('http://127.0.0.1:' + port + '/json'))
    print('Targets:', [(t.get('type'), t.get('url')) for t in tabs], flush=True)
    target = next(t for t in tabs if t.get('type') == 'page')
    ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=10)
    serial = 0

    def call(method, params=None):
        global serial
        serial += 1
        ws.send(json.dumps({'id': serial, 'method': method, 'params': params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == serial:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result', {})

    def evaluate(expression):
        result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def load(mode):
        marker = str(time.time_ns())
        call('Page.navigate', {'url': 'http://127.0.0.1:%d/design/ui-preview.html?mode=%s&run=%s' % (server.server_port, mode, marker)})
        for _ in range(100):
            time.sleep(.05)
            if evaluate('location.search.includes(' + json.dumps(marker) + ') && document.documentElement.hasAttribute("data-preview-results")'):
                break
        evaluate('new Promise(resolve=>setTimeout(resolve,250))')
        checks = evaluate('JSON.parse(document.documentElement.getAttribute("data-preview-results"))')
        assert checks and all(c['pass'] for c in checks), (mode, checks)
        return checks

    call('Page.enable')
    for width in [360, 390, 768, 1280]:
        height = 640 if width < 600 else 900
        call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
        for theme in ['light', 'dark']:
            call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
            for mode in ['today', 'week']:
                checks = load(mode)
                metrics = evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,height:innerHeight})')
                assert metrics['width'] == width and metrics['scroll'] <= width, metrics
                assert evaluate('performance.getEntriesByType("resource").every(r=>r.name.startsWith(location.origin+"/")||r.name.startsWith("data:"))')
                png = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
                name = '%s-%d-%s.png' % (mode, width, theme)
                (ROOT / 'design/screenshots' / name).write_bytes(base64.b64decode(png['data']))
                results.append({'screenshot': name, 'metrics': metrics, 'checks': checks})
    call('Emulation.setDeviceMetricsOverride', {'width': 360, 'height': 640, 'deviceScaleFactor': 1, 'mobile': False})
    for mode in ['weekend', 'empty', 'gate', 'expired', 'lock', 'no-data', 'network', 'bounds', 'sheet', 'periods', 'unconfigured', 'xss']:
        results.append({'mode': mode, 'checks': load(mode)})
    load('empty')
    assert evaluate("document.querySelector('.next-course').getAttribute('aria-label').startsWith('下一次上课，')")
    assert evaluate("!document.getElementById('week-label').hasAttribute('aria-label') && document.getElementById('week-label').title === '回到本周'")
    results.append({'accessible_week_and_next_course_names': True})
    load('weekend')
    for count in [6, 7]:
        if count == 7:
            evaluate("fixture.courses.push({name:'Sunday',room:'D404',teachers:'Demo',day:6,units:[0,1],weeks:[8]});document.getElementById('week-label').click()")
        metrics = evaluate("({min:parseFloat(document.getElementById('grid').style.minWidth),outer:document.documentElement.scrollWidth,viewport:innerWidth,scroll:document.getElementById('grid-scroll').scrollWidth,client:document.getElementById('grid-scroll').clientWidth})")
        assert metrics['min'] >= 24 + count * 56 + (count + 1) * 2, (count, metrics)
        assert evaluate("document.querySelector('#grid thead th:nth-child(2)').getBoundingClientRect().width") >= 56
        assert metrics['outer'] <= metrics['viewport'] and metrics['scroll'] > metrics['client']
        results.append({'columns': count, 'metrics': metrics})
    label = evaluate("document.getElementById('week-label').textContent")
    evaluate("document.getElementById('grid-scroll').focus()")
    call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'ArrowRight', 'code': 'ArrowRight', 'windowsVirtualKeyCode': 39})
    call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'ArrowRight', 'code': 'ArrowRight', 'windowsVirtualKeyCode': 39})
    evaluate('new Promise(resolve=>setTimeout(resolve,300))')
    assert evaluate("document.getElementById('week-label').textContent") == label
    assert evaluate("document.getElementById('grid-scroll').scrollLeft") > 0
    evaluate("document.getElementById('week-next').focus()")
    call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'ArrowRight', 'code': 'ArrowRight', 'windowsVirtualKeyCode': 39})
    assert evaluate("document.getElementById('week-label').textContent") != label
    call('Emulation.setEmulatedMedia', {'media': 'print'})
    assert evaluate("getComputedStyle(document.getElementById('week-label')).display") != 'none'
    assert evaluate("getComputedStyle(document.getElementById('week-next')).display") == 'none'
    assert evaluate("getComputedStyle(document.getElementById('pane-today')).display") != 'none'
    assert evaluate("getComputedStyle(document.getElementById('pane-week')).display") != 'none'
    results.append({'keyboard_scroll_and_week_navigation': True, 'print_week_heading': True})
    call('Emulation.setEmulatedMedia', {'media': ''})
    for mode in ['today', 'gate']:
        load(mode)
        evaluate("window.loggedErrors=[];console.error=function(e){loggedErrors.push(String(e))};fixture.courses=[null]")
        if mode == 'today':
            evaluate("document.getElementById('fatal-retry').click()")
        else:
            evaluate("window.fetch=function(path){return Promise.resolve({status:200,json:function(){return Promise.resolve(path==='/api/login'?{token:'synthetic'}:fixture)}})};document.getElementById('gate-input').value='demo';document.getElementById('gate-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        evaluate('new Promise(resolve=>setTimeout(resolve,100))')
        assert evaluate("document.getElementById('fatal-text').textContent") == '\u9875\u9762\u51fa\u9519\u4e86\uff0c\u8bf7\u5237\u65b0'
        assert evaluate('loggedErrors.length') == 1
        results.append({'render_error_from': mode, 'generic_message_and_console_error': True})
    (ROOT / 'design/t06-browser-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('16 emulated screenshots and 12 state checks passed')
finally:
    process.terminate()
    process.wait(timeout=10)
    server.shutdown()
    try:
        profile.cleanup()
    except PermissionError:
        pass
