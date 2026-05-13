from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    UnfollowEvent,
)
from app.config import LINE_CHANNEL_ACCESS_TOKEN

_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)


def _reply(reply_token: str, text: str) -> None:
    with ApiClient(_config) as client:
        api = MessagingApi(client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def handle_message(event: MessageEvent) -> None:
    if not isinstance(event.message, TextMessageContent):
        return
    user_text = event.message.text.strip()
    _reply(event.reply_token, f"你說：{user_text}")


def handle_follow(event: FollowEvent) -> None:
    _reply(event.reply_token, "歡迎加入！有任何問題歡迎留言 🎉")


def handle_unfollow(event: UnfollowEvent) -> None:
    pass
