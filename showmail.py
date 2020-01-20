#!/usr/bin/env python3

# TODO: sorting
# TODO: escaping
# TODO: docker

import re
from html import escape
from string import Template
from functools import partial
from collections import namedtuple
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, test
from email.header import make_header, decode_header
from mailbox import Maildir
from urllib.parse import quote, unquote

MessagePart = namedtuple('MessagePart', 'type content')

def header_to_str(header):
  return str(make_header(decode_header(header)))

class MessageAdapter:
  def __init__(self, message):
    self.message = message
    self.subject = header_to_str(message['Subject'])
    self.date = header_to_str(message['Date'])
    self.addr_to = header_to_str(message['To'])
    self.addr_from = header_to_str(message['From'])
    self.parts = {i: p.get_content_type() for i, p in enumerate(message.walk())}

  def __repr__(self):
    return f'Message(subject={self.subject})'

  def part(self, i):
    parts = dict(enumerate(self.message.walk()))
    part = parts[i]

    type = part.get_content_type()
    charset = part.get_content_charset('utf-8')

    if (part.is_multipart()):
      content = ''
    elif type in ['text/plain', 'text/html']:
      content = part.get_payload(decode=True).decode(charset)
    else:
      content = part.get_payload(decode=True)

    return MessagePart(type, content)

class MaildirAdapter(Mapping):
  def __init__(self, maildir_path):
    self.mbox = Maildir(maildir_path, create=False)

  def __getitem__(self, key):
    actual_key = unquote(key)
    msg = self.mbox[actual_key]
    return MessageAdapter(msg)

  def __iter__(self):
    return iter(map(quote, self.mbox.keys()))

  def __len__(self):
    return len(self.mbox)

PATH_RE = re.compile('^/(?P<id>[^/]+)/(?P<part>\d+)$')
HTML_TPL = Template('<!DOCTYPE html><html><head></head><body>$content</body></html>')
MSG_TPL = Template('<div><h2>$subject</h2><p>Date: $date</p><ul>$links</ul></div>')
LINK_TPL = Template('<li><a href="/$id/$part">$type</a></li>')

class MaildirHTTPRequestHandler(BaseHTTPRequestHandler):
  def __init__(self, *args, maildir_path, **kwargs):
    self.maildir = MaildirAdapter(maildir_path)
    super().__init__(*args, **kwargs)

  def do_GET(self):
    if self.path == '/':
      self.list_messages()
      return

    m = PATH_RE.match(self.path)
    if (m):
      self.message_part(*m.groups())
      return

    self.not_found()

  def html(self, code, text, type='text/html'):
    encoded = text.encode()
    self.send_response(code)
    self.send_header("Content-Type", type + "; charset=utf-8")
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    self.wfile.write(encoded)

  def list_messages(self):
    content = []
    for id, m in self.maildir.items():
      links = []
      for part, type in m.parts.items():
        links.append(LINK_TPL.substitute(id=id, part=part, type=type))
      content.append(MSG_TPL.substitute(id=id, subject=m.subject, date=m.date, links=''.join(links)))

    resp = HTML_TPL.substitute(content=''.join(content))
    self.html(HTTPStatus.OK, resp)

  def message_part(self, id, part):
    p = self.maildir[id].part(int(part))
    self.html(HTTPStatus.OK, p.content, type=p.type)

  def not_found(self):
    self.html(HTTPStatus.NOT_FOUND, 'Error: Not Found')

if __name__ == '__main__':
  import os
  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument('--directory', '-d', default=os.getcwd(),
      help='Specify alternative directory '
           '[default:current directory]')
  parser.add_argument('port', action='store',
      default=8000, type=int,
      nargs='?',
      help='Specify alternate port [default: 8000]')

  args = parser.parse_args()

  handler = partial(MaildirHTTPRequestHandler, maildir_path=args.directory)

  test(handler, port=args.port)
