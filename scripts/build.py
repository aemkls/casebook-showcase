"""Build the static page with inline assets for Streamlit's static-file handler."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]


def render():
    source = ROOT / 'frontend'
    page = (source / 'index.html').read_text(encoding='utf-8')
    worker = '\n'.join((source / name).read_text(encoding='utf-8') for name in ('search.js', 'worker.js'))
    assets = {
        'STYLES': (source / 'style.css').read_text(encoding='utf-8'),
        'WORKER': worker.replace('</script', '<\\/script'),
        'APP': (source / 'app.js').read_text(encoding='utf-8').replace('</script', '<\\/script'),
    }
    for key, content in assets.items():
        page = page.replace('{{' + key + '}}', content)
    return page


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check that the committed HTML is current')
    args = parser.parse_args()
    target = ROOT / 'static' / 'practice.html'
    built = render()
    if args.check:
        if not target.exists() or target.read_text(encoding='utf-8') != built:
            raise SystemExit('static/practice.html is out of date. Run python scripts/build.py')
        print('Static page is up to date.')
    else:
        target.parent.mkdir(exist_ok=True)
        target.write_text(built, encoding='utf-8')
        print(f'Built {target.relative_to(ROOT)} ({len(built.encode()):,} bytes)')
