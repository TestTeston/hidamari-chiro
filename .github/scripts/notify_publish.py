#!/usr/bin/env python3
"""新しいブログ記事が公開された時に院長にメール通知する。

Jekyllビルド成功後にGitHub Actionsから呼ばれる。
今日付の _posts/ファイルが存在すれば、Googleマップ投稿用の
テキストを含めた通知メールを送る。
ただしデプロイ前（--precheck）に本番を確認し、すでに公開済みの
記事には送らない（同じ日に何度pushしても通知は1記事1回）。
"""

from __future__ import annotations

import datetime
import glob
import os
import re
import smtplib
import sys
import unicodedata
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


def clean_email(value: str) -> str:
    """全角文字（＠やａなど）を半角に正規化し前後空白を除去する。
    IMEがONのまま入力したメールアドレスを救済する。"""
    return unicodedata.normalize("NFKC", value or "").strip()

JST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(JST).strftime("%Y-%m-%d")
TODAY_COMPACT = TODAY.replace("-", "")


def parse_post(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # ファイル名 (YYYY-MM-DD-title.md) から公開日を取り出してURLを組み立てる
    # （permalink: /blog/:year:month:day.html に対応）
    fn = os.path.basename(path)
    dm = re.match(r"(\d{4})-(\d{2})-(\d{2})", fn)
    date_compact = "".join(dm.groups()) if dm else TODAY_COMPACT

    m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not m:
        raise ValueError(f"フロントマターを解析できません: {path}")
    frontmatter, body = m.groups()

    def get(key: str) -> str:
        m = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
        return m.group(1).strip().strip('"').strip("'") if m else ""

    excerpt_lines: list[str] = []
    for raw in body.strip().split("\n"):
        line = raw.strip()
        if not line:
            if excerpt_lines:
                break
            continue
        if line.startswith("!") or line.startswith("#"):
            continue
        # [文字](URL) のリンク記法は文字だけ残す
        clean = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
        clean = re.sub(r"[\*_`]", "", clean)
        clean = re.sub(r"\\$", "", clean)
        if clean:
            excerpt_lines.append(clean)
        if len(excerpt_lines) >= 3:
            break
    excerpt = "\n".join(excerpt_lines) or body.strip()[:200]

    return {
        "title": get("title"),
        "category": get("category"),
        "date": get("date"),
        "excerpt": excerpt,
        "url": f"https://www.hidamari-chiro.jp/blog/{date_compact}.html",
    }


def build_email_body(post: dict) -> str:
    return f"""新しいブログ記事が公開されました 🎉

【記事情報】
タイトル：{post['title']}
カテゴリ：{post['category']}
公開日　：{post['date']}
URL　　 ：{post['url']}

─────────────────────
📋 Googleマップ投稿用テキスト（コピペ用）
─────────────────────

{post['title']}

ブログを更新しました。
{post['excerpt']}

詳しくはこちら：
{post['url']}

─────────────────────

👉 上記を Google Business Profile の投稿画面にコピペしてください
📱 投稿画面：https://business.google.com/posts

このメールは GitHub Actions から自動送信されています。
"""


def send_mail(post: dict) -> None:
    user = clean_email(os.environ["GMAIL_USER"])
    # アプリパスワードは表示上スペース区切りだが実際はスペース不要
    password = os.environ["GMAIL_PASSWORD"].replace(" ", "").strip()

    msg = MIMEMultipart()
    msg["From"] = formataddr(("ひだまりHP通知", user), charset="utf-8")
    msg["To"] = user
    msg["Subject"] = f"📢 新ブログ公開: {post['title']}"
    msg.attach(MIMEText(build_email_body(post), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


def is_live(url: str) -> bool | None:
    """本番にページがあれば True、なければ False、確認できなければ None。
    CDNのキャッシュ（古い404）を避けるため、毎回違うクエリを付ける。"""
    bust = f"{url}?check={int(datetime.datetime.now().timestamp())}"
    try:
        with urllib.request.urlopen(bust, timeout=15) as res:
            return res.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:
        return None


def precheck() -> int:
    """デプロイ前に呼ぶ。今日付の記事のうち、まだ本番に出ていないもの
    （＝今回が初公開のもの）だけを GITHUB_OUTPUT の new_posts に書き出す。
    pushのたびにビルドが走っても、通知が1記事1回になるようにするため。"""
    new_posts = []
    for path in sorted(glob.glob(f"_posts/{TODAY}-*.md")):
        live = is_live(parse_post(path)["url"])
        if live:
            print(f"公開済みのため通知しない: {path}")
        else:
            # 確認できなかった時（None）は、通知漏れを避けて送る側に倒す
            print(f"初公開として通知する: {path}" + ("（公開状況を確認できず）" if live is None else ""))
            new_posts.append(path)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"new_posts={'|'.join(new_posts)}\n")
    return 0


def main() -> int:
    if "--precheck" in sys.argv:
        return precheck()

    posts = sorted(glob.glob(f"_posts/{TODAY}-*.md"))
    test_mode = os.environ.get("NOTIFY_TEST", "").strip().lower() == "true"

    # precheck の結果があれば、初公開の記事だけに絞る（テストモードは除く）
    if "NEW_POSTS" in os.environ and not test_mode:
        new_posts = set(filter(None, os.environ["NEW_POSTS"].split("|")))
        posts = [p for p in posts if p in new_posts]

    if not posts and test_mode:
        all_posts = sorted(glob.glob("_posts/*.md"))
        if all_posts:
            posts = [all_posts[-1]]
            print(f"[テストモード] 最新記事で通知テスト: {posts[0]}")

    if not posts:
        print(f"今日（{TODAY}）初公開の記事なし。通知スキップ。")
        return 0

    for path in posts:
        post = parse_post(path)
        send_mail(post)
        print(f"通知メール送信完了: {post['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
