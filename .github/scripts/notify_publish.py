#!/usr/bin/env python3
"""新しいブログ記事が公開された時に院長にメール通知する。

Jekyllビルド成功後にGitHub Actionsから呼ばれる。
今日付の _posts/ファイルが存在すれば、Googleマップ投稿用の
テキストを含めた通知メールを送る。
"""

from __future__ import annotations

import datetime
import glob
import os
import re
import smtplib
import sys
import unicodedata
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
        clean = re.sub(r"[\*_`]", "", line)
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


def main() -> int:
    posts = sorted(glob.glob(f"_posts/{TODAY}-*.md"))
    test_mode = os.environ.get("NOTIFY_TEST", "").strip().lower() == "true"

    if not posts and test_mode:
        all_posts = sorted(glob.glob("_posts/*.md"))
        if all_posts:
            posts = [all_posts[-1]]
            print(f"[テストモード] 最新記事で通知テスト: {posts[0]}")

    if not posts:
        print(f"今日（{TODAY}）公開の新規記事なし。通知スキップ。")
        return 0

    for path in posts:
        post = parse_post(path)
        send_mail(post)
        print(f"通知メール送信完了: {post['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
