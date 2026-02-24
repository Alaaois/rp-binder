from typing import Any, TypedDict


class PhraseItem(TypedDict, total=False):
    item_id: str
    title: str
    text: str
    hotkey: str
    send_mode: str
    delay_ms: int
    chat_open_hotkey: str
    chat_open_delay_ms: int
    chat_send_each_line: bool
    enabled: bool
    variables: list[str]
    tags: list[str]
    requires_input: bool


class Category(TypedDict):
    name: str
    items: list[PhraseItem]


class Profile(TypedDict):
    profile_name: str
    categories: list[Category]


class ProfilesPayload(TypedDict):
    version: str
    profiles: list[Profile]


class UserSettings(TypedDict):
    nick: str
    position: str
    binder_enabled: bool
    panic_hotkey: str


JsonDict = dict[str, Any]
