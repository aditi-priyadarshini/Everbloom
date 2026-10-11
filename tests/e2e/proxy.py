"""Supabase-compatible front door: /rest/v1/* -> PostgREST, /storage/v1/* -> in-memory stub."""
import http.client, json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
PG=('127.0.0.1',3000); OBJECTS={}
class H(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*a): pass
    def _send(self,code,body=b'',headers=None):
        self.send_response(code)
        for k,v in (headers or {}).items():
            if k.lower() not in ('transfer-encoding','connection','server','date'): self.send_header(k,v)
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def _handle(self):
        n=int(self.headers.get('Content-Length') or 0); body=self.rfile.read(n) if n else b''
        p=self.path
        if p.startswith('/rest/v1/') or p=='/rest/v1':
            c=http.client.HTTPConnection(*PG,timeout=30)
            hdr={k:v for k,v in self.headers.items() if k.lower() not in ('host','content-length','connection')}
            c.request(self.command,p[len('/rest/v1'):] or '/',body=body or None,headers=hdr)
            r=c.getresponse(); data=r.read(); self._send(r.status,data,dict(r.getheaders())); return
        if p.startswith('/storage/v1/'):
            if '/object/sign/' in p: self._send(200,json.dumps({'signedURL':'/object/sign/x?token=t'}).encode(),{'Content-Type':'application/json'}); return
            if self.command=='GET' and '/bucket/' in p: self._send(200,json.dumps({'id':'b','public':True}).encode(),{'Content-Type':'application/json'}); return
            if self.command=='POST' and '/object/' in p: OBJECTS[p]=len(body); self._send(200,json.dumps({'Key':p}).encode(),{'Content-Type':'application/json'}); return
            self._send(200,b'{}',{'Content-Type':'application/json'}); return
        self._send(404,b'{}')
    do_GET=do_POST=do_PATCH=do_PUT=do_DELETE=do_HEAD=_handle
ThreadingHTTPServer(('127.0.0.1',8081),H).serve_forever()
