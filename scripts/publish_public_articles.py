"""Publish JSON article files through the protected public article API."""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def request(url, method, token, body, content_type):
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Article API returned HTTP {exc.code}") from None


def multipart_image(url, token, filename):
    boundary = "----KinoPubObserverArticleUploadBoundary"
    mime = mimetypes.guess_type(filename.name)[0] or "application/octet-stream"
    image = filename.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + image + f"\r\n--{boundary}--\r\n".encode()
    result = request(url, "POST", token, body, f"multipart/form-data; boundary={boundary}")
    return result["src"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="content/public-articles")
    parser.add_argument("--assets-dir", default="data/public-articles-source")
    parser.add_argument("--base-url", default=os.getenv("PUBLIC_ARTICLE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--slug", help="Publish one article by its filename slug")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kinopub_parser.settings")
    import django

    django.setup()
    from django.conf import settings

    token = settings.PUBLIC_ARTICLE_API_TOKEN
    if not token:
        sys.exit("PUBLIC_ARTICLE_API_TOKEN is not configured in this environment")

    directory = Path(args.directory)
    assets = Path(args.assets_dir)
    files = [directory / f"{args.slug}.json"] if args.slug else sorted(directory.glob("*.json"))
    if not files or any(not file.is_file() for file in files):
        sys.exit("No matching article JSON files found")

    base = args.base_url.rstrip("/")
    for path in files:
        article = json.loads(path.read_text(encoding="utf-8"))
        slug = path.stem

        def upload_asset(image):
            if not isinstance(image, dict):
                return
            source = image.get("src", "")
            if source.startswith("asset:"):
                local_image = assets / source.removeprefix("asset:")
                if not local_image.is_file():
                    raise FileNotFoundError(f"Article image not found: {local_image}")
                image["src"] = multipart_image(
                    f"{base}/api/internal/articles/assets/{slug}/", token, local_image
                )

        for block in article.get("content_blocks", []):
            upload_asset(block)
            # Procedure screenshots are nested on their matching step, so each
            # action keeps its own evidence and the same protected asset flow.
            upload_asset(block.get("image"))
        request(
            f"{base}/api/internal/articles/{slug}/",
            "PUT",
            token,
            json.dumps(article, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )
        print(f"Published {slug}")


if __name__ == "__main__":
    main()
