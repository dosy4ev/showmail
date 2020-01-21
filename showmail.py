#!/usr/bin/env python3

import re
import time

from html import escape
from string import Template
from functools import partial
from collections import namedtuple
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, test
from email.utils import parsedate
from email.header import make_header, decode_header
from mailbox import Maildir
from urllib.parse import quote, unquote

MessagePart = namedtuple('MessagePart', 'type content')

def header_to_str(header):
  return str(make_header(decode_header(header)))
            
def extract_date(item):
  return time.mktime(parsedate(item[1].date))

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

class HTMLTemplate:
  def __init__(self, template):
    self.template = Template(template)

  def substitute(*args, **kwargs):
    if not args:
      raise TypeError("descriptor 'substitute' of 'HTMLTemplate' object needs an argument")
    self, *args = args  # allow the "self" keyword be passed
    if len(args) > 1:
      raise TypeError('Too many positional arguments')
    if not args:
      mapping = kwargs
    elif kws:
      mapping = _ChainMap(kwargs, args[0])
    else:
      mapping = args[0]
    escaped_mapping = {k: v if k.startswith('raw_') else escape(str(v)) for k, v in mapping.items()}

    return self.template.substitute(escaped_mapping)

PATH_RE = re.compile('^/(?P<id>[^/]+)/(?P<part>\d+)$')
HTML_TPL = HTMLTemplate('<!DOCTYPE html><html><head></head><body>\n$raw_content\n</body></html>')
MSG_TPL = HTMLTemplate('<div><h2>$subject</h2><p>Date: $date</p>'
                       '<p>From: $addr_from</p><p>To: $addr_to</p><ul>$raw_links</ul></div><hr>\n')
LINK_TPL = HTMLTemplate('<li><a href="/$id/$part">$type</a></li>')

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
    for id, m in sorted(self.maildir.items(), key=extract_date, reverse=True):
      links = []
      for part, type in m.parts.items():
        links.append(LINK_TPL.substitute(id=id, part=part, type=type))
      content.append(MSG_TPL.substitute(id=id, subject=m.subject, date=m.date, addr_from=m.addr_from,
                                        addr_to=m.addr_to, raw_links=''.join(links)))

    resp = HTML_TPL.substitute(raw_content=''.join(content))
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

