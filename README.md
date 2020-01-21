# Showmail

`showmail` is a simple python3 script to view [maildir](https://ru.wikipedia.org/wiki/Maildir) in web browser.

## Usage

`showmail` does not have any dependencies other than python3 standard library.

```
python3 showmail.py [-d /path/to/maildir] [custom_port]
```

or with docker:

```
docker run -d -v /path/to/maildir:/mail -p custom_port:8000 showmail_image
```

## License

[Unlicense](https://unlicense.org)
