"""Seed the 汽美短影音爆款衝刺包 v1.0 sprint into social_distributor.

5 cards × 1 AccountGroup「PopMonster 主推」(FB + IG + TikTok) = 15 PostTarget
rows scheduled 2026-05-17 21:00 → 2026-05-21 21:00 Asia/Taipei.

Usage:
    cd social_distributor/backend
    source .venv/bin/activate
    # 1) Fill MEDIA_MANIFEST below with media_assets.id for each card
    # 2) Preview
    python -m scripts.seed_sprint_v1 --dry-run
    # 3) Commit
    python -m scripts.seed_sprint_v1
"""
import argparse
import sys

from app import create_app
from app.extensions import db
from app.models import AccountGroup, MediaAsset, Post

# Fill these by running the Step 1 SQL probe and pairing each card to its
# pre-uploaded video's media_assets.id. Leave None to abort with a clear error.
MEDIA_MANIFEST: dict[int, int | None] = {
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
}

GROUP_NAME = "PopMonster 主推"
TZ = "Asia/Taipei"

CARDS = [
    (
        2,
        "2026-05-17T21:00:00",
        "99% 的 愛車一族 正在親手 搞砸 自己的漆面",
        """99% 愛車一族每週都在親手搞砸自己的漆面
五個錯誤你一定犯過至少三個
不預洗直接擦就是砂紙磨漆
留言想要送你五大錯誤對應解法卡

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #洗車錯誤 #兩桶水法 #漆面保養 #新手洗車""",
    ),
    (
        5,
        "2026-05-18T20:30:00",
        "90% 的 黑車車主 不知不覺都在 毀掉 幾十萬的車漆",
        """90% 黑車車主不知不覺都在毀掉自己幾十萬的車漆
黑車不掩飾任何瑕疵
白車的紋黑車放大十倍
黑車三鐵律 時間 毛巾 即時擦水
留言黑車送你黑車專屬清單

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #黑車保養 #黑車車主 #太陽紋 #黑色烤漆""",
    ),
    (
        3,
        "2026-05-19T21:00:00",
        "大部分 新手車主 正在每週 加速氧化 車漆鍍膜",
        """大部分新手車主每週都在加速氧化自己的鍍膜
你花一萬五的鍍膜被 39 塊的洗車精洗掉
強鹼強酸洗碗精全部不能用
留言鍍膜送你中性洗劑判斷清單

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #鍍膜車保養 #中性洗劑 #鍍膜禁忌 #汽車鍍膜""",
    ),
    (
        1,
        "2026-05-20T20:30:00",
        "七成 黑車車主 正在親手 刮花 輪圈",
        """七成黑車車主正在親手刮花輪圈
你以為輪圈用洗車身那塊毛巾就好嗎
那塊毛巾上的鐵屑等於砂紙
輪圈刮花一次拋光要花兩萬
留言區置頂有完整輪圈三件套清單
打 1 我私訊你

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #輪圈刮花 #黑色輪圈 #輪圈護理 #台中汽車美容""",
    ),
    (
        4,
        "2026-05-21T21:00:00",
        "90% 的 老車主 每次洗車都在 報廢 幾十萬的車漆",
        """90% 老車主每週都在自助洗車場報廢自己幾十萬的車漆
高壓水柱 80 到 120 bar 貼太近就是吃漆
循環水裡的沙石是上一台車刷下來的
留言自助送你完整自助場 SOP

#米速 #泡泡怪獸 #汽車美容 #拋光 #鍍膜 #自助洗車場 #老車保養 #高壓清洗 #洗車場SOP""",
    ),
]


def main(dry_run: bool) -> int:
    missing = [k for k, v in MEDIA_MANIFEST.items() if v is None]
    if missing:
        print(
            f"ERROR: MEDIA_MANIFEST 缺 card_id={missing},請先跑 Step 1 SQL 查 media_assets.id 後填入",
            file=sys.stderr,
        )
        return 2

    app = create_app()
    with app.app_context():
        group = (
            db.session.query(AccountGroup).filter_by(name=GROUP_NAME).one_or_none()
        )
        if not group:
            print(f"ERROR: AccountGroup '{GROUP_NAME}' 不存在", file=sys.stderr)
            return 3
        active = [a for a in group.accounts if a.revoked_at is None]
        platforms = sorted({a.platform.value for a in active})
        print(
            f"Group {group.id} '{group.name}' has {len(active)} active accounts: {platforms}"
        )

        for card_id, mid in MEDIA_MANIFEST.items():
            if not db.session.get(MediaAsset, mid):
                print(
                    f"ERROR: 卡 {card_id} 對應 media_id={mid} 不存在於 media_assets",
                    file=sys.stderr,
                )
                return 4

        client = app.test_client()

        for card_id, scheduled_local, title, caption in CARDS:
            post = Post(
                user_id=group.user_id,
                title=title,
                caption=caption,
                media_id=MEDIA_MANIFEST[card_id],
            )
            db.session.add(post)
            db.session.commit()

            payload = {
                "group_ids": [group.id],
                "scheduled_for": scheduled_local,
                "timezone": TZ,
                "jitter_minutes": 0,
                "generate_variants": False,
                "dry_run": dry_run,
            }
            resp = client.post(f"/api/posts/{post.id}/distribute", json=payload)
            body = resp.get_json() or {}
            print(
                f"card {card_id} → post_id={post.id} | http={resp.status_code} | "
                f"targets={body.get('created_target_ids')} | dry_run={dry_run}"
            )
            if resp.status_code not in (200, 201):
                print(f"  FAIL body: {body}", file=sys.stderr)
                return 5

            if dry_run:
                for entry in body.get("plan", []):
                    preview = entry["preview_caption"][:60]
                    print(
                        f"   ↳ {entry['platform']:10} @ {entry['scheduled_for']}  "
                        f"caption_preview={preview!r}"
                    )
                db.session.delete(post)
                db.session.commit()

    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    raise SystemExit(main(args.dry_run))
